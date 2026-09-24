"""
对话式行程规划的图。

流程：
    START -> clarify (可能interrupt) -> plan -> feedback(interrupt)
    feedback -> [满意] -> END
    feedback -> [想改] -> revise -> feedback(循环)
"""

import logging
import re
from typing import TypedDict,Optional,Literal
from app.schemas import FeedbackIntent, TripRequest,Attraction,Hotel, TravelIntent
from langgraph.types import interrupt
from app.graph.workflow import run_workflow
from langgraph.graph import StateGraph,START,END
from app.agents.tools import get_session
from app.agents.revise_tools import apply_revision, get_ctx as get_revision_context
from datetime import date,datetime
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage,HumanMessage
from langchain_deepseek import ChatDeepSeek
from app.agents.intent import parse_travel_intent
from app.agents.plan_validator import remove_cross_day_duplicates, validate_plan
from app.db.preferences_store import get_preferences

logger = logging.getLogger(__name__)

feedback_llm = ChatDeepSeek(model="deepseek-chat",temperature=0.6)
feedback_classifier_llm = ChatDeepSeek(model="deepseek-chat", temperature=0)

# 整个图的共享状态
class ConversationState(TypedDict):
    request: TripRequest
    intent: TravelIntent
    trip_plan: Optional[dict]
    raw_attractions:list[Attraction]
    raw_hotels:list[Hotel]
    last_feedback:Optional[str]
    token_used: int
    revise_note: Optional[str]
    feedback_intent: Optional[FeedbackIntent]
    feedback_answer: Optional[str]

async def intent_node(state:ConversationState, config: RunnableConfig) -> dict:
    req = state["request"]
    user_id = config.get("configurable", {}).get("user_id", "")
    saved_preferences = None
    if user_id:
        try:
            saved_preferences = await get_preferences(user_id)
        except Exception:
            logger.exception("[Intent] 读取长期偏好失败，继续使用本次请求")
    intent = await parse_travel_intent(req, saved_preferences=saved_preferences)
    return {"intent":intent}

def find_visit_conflicts(intent:TravelIntent) -> list[str]:
    avoided = set(intent.avoid_places)
    return [place for place in intent.must_visit if place in avoided]

def resolve_visit_conflict(
        intent:TravelIntent,
        place:str,
        decision:Literal["visit","avoid"],
) -> TravelIntent:
    data = intent.model_dump() # itent是一个TravelIntent对象，不是一个普通字典
    if decision == "visit":
        data["avoid_places"] = [item for item in data["avoid_places"] if item != place]
    elif decision == "avoid":
        data["must_visit"] = [item for item in data["must_visit"] if item != place]
    else:
        raise ValueError(f"未知的冲突处理决定：{decision}")
    conflict_message = f"地点‘{place}’同时出现在必去和不想去列表中"
    data["ambiguities"] = [i for i in data["ambiguities"] if i != conflict_message]
    return TravelIntent.model_validate(data)

def parse_visit_decision(
        answer:str
) -> Literal["visit","avoid"] | None:
    normalized = answer.strip()
    if normalized in {"去", "要去", "保留"}:
        return "visit"

    if normalized in {"不去", "避开", "删除"}:
        return "avoid"

    return None


def find_budget_ambiguities(intent: TravelIntent) -> list[str]:
    return [item for item in intent.ambiguities if "预算" in item]


def resolve_budget_answer(
    intent: TravelIntent,
    answer: str,
    trip_days: int,
) -> TravelIntent | None:
    normalized = answer.strip()
    amounts = re.findall(r"\d+", normalized.replace(",", ""))
    amount = int(amounts[0]) if amounts else None

    if "人均" in normalized:
        return None
    if any(marker in normalized for marker in ("每天", "每日")):
        if amount is None:
            return None
        budget_limit = amount * trip_days
    elif any(marker in normalized for marker in ("总预算", "全程", "总额", "一共")):
        budget_limit = amount if amount is not None else intent.budget_limit
    elif amount is not None:
        budget_limit = amount
    else:
        return None

    if budget_limit is None or budget_limit <= 0:
        return None
    data = intent.model_dump()
    data["budget_limit"] = budget_limit
    data["ambiguities"] = [
        item for item in data["ambiguities"] if "预算" not in item
    ]
    return TravelIntent.model_validate(data)


def merge_travel_intents(base: TravelIntent, update: TravelIntent) -> TravelIntent:
    data = base.model_dump()
    list_fields = (
        "must_visit",
        "avoid_places",
        "themes",
        "traveler_types",
        "accessibility_needs",
        "dietary_restrictions",
        "hotel_requirements",
        "time_requirements",
        "excluded_activities",
        "special_requests",
        "ambiguities",
    )
    for field in list_fields:
        data[field] = list(dict.fromkeys([*data[field], *getattr(update, field)]))

    if update.must_visit:
        data["avoid_places"] = [
            item for item in data["avoid_places"] if item not in update.must_visit
        ]
    if update.avoid_places:
        data["must_visit"] = [
            item for item in data["must_visit"] if item not in update.avoid_places
        ]
    if update.pace != "normal":
        data["pace"] = update.pace
    if update.activity_environment != "mixed":
        data["activity_environment"] = update.activity_environment
    if update.budget_limit is not None:
        data["budget_limit"] = update.budget_limit
    if update.budget_level is not None:
        data["budget_level"] = update.budget_level

    return TravelIntent.model_validate(data)


def classify_feedback_by_rule(feedback: str) -> FeedbackIntent | None:
    normalized = feedback.strip().lower()
    if not normalized:
        return FeedbackIntent(action="unknown")

    explicit_finish_phrases = ("挺好的", "就这样", "按这个来", "不用改了")
    contrast_markers = ("但", "不过", "但是", "还要", "还得", "需要", "请")
    if (
        any(phrase in normalized for phrase in explicit_finish_phrases)
        and not any(marker in normalized for marker in contrast_markers)
    ):
        return FeedbackIntent(action="finish")

    revision_markers = {
        "但", "改", "修改", "调整", "换", "删", "增加", "添加", "取消",
        "轻松点", "太赶", "太累", "不要", "不吃", "降低", "提高", "改成",
    }
    if any(marker in normalized for marker in revision_markers):
        revision_type = "other"
        if any(marker in normalized for marker in ("景点", "换", "删", "增加", "添加")):
            revision_type = "attractions"
        elif "酒店" in normalized:
            revision_type = "hotel"
        elif any(marker in normalized for marker in ("轻松", "太赶", "太累", "节奏")):
            revision_type = "pace"
        elif "交通" in normalized:
            revision_type = "transport"
        elif "预算" in normalized:
            revision_type = "budget"
        elif any(marker in normalized for marker in ("餐", "吃", "忌口")):
            revision_type = "meals"
        return FeedbackIntent(action="revise", revision_type=revision_type)

    finish_phrases = {
        "满意", "ok", "可以", "没问题", "完成", "done", "结束", "好",
    }
    if normalized in finish_phrases:
        return FeedbackIntent(action="finish")

    if any(marker in normalized for marker in ("?", "？", "吗", "么", "什么", "为什么", "怎么", "是否")):
        return FeedbackIntent(action="question")
    return None


async def classify_feedback(feedback: str) -> FeedbackIntent:
    ruled = classify_feedback_by_rule(feedback)
    if ruled is not None:
        return ruled

    classifier = feedback_classifier_llm.with_structured_output(FeedbackIntent)
    try:
        return await classifier.ainvoke(
            [
                SystemMessage(content=(
                    "判断用户对旅行计划的反馈类型。包含任何修改要求时必须选择 revise；"
                    "只表达满意时选择 finish；只询问信息时选择 question；无法判断选 unknown。"
                )),
                HumanMessage(content=feedback),
            ]
        )
    except Exception:
        logger.exception("[Feedback] 分类失败")
        return FeedbackIntent(action="unknown")

def summarize_plan_for_feedback(plan:Optional[dict]) -> str:
    if not plan:
        return "暂无行程"

    lines = [
        f"目的地：{plan.get('destination','')}",
        f"天数：{plan.get('trip_days','')}",
    ]
    for dp in plan.get("daily_plans",[]):
        attractions = "、".join(dp.get("attraction_names",[]))
        lines.append(f"Day {dp.get('day')}：{attractions}")
    hotels = plan.get("hotels") or []
    if hotels:
        lines.append(f"酒店：{'、'.join(h.get('name','') for h in hotels[:3])}")
    return "\n".join(lines)

def fallback_feedback_question(last_feedback:Optional[str]) -> str:
    feedback = (last_feedback or "").strip()
    if feedback:
        return "我按你的反馈调了一版，你看看现在顺不顺。还有哪里别扭，直接说。"
    return "我先把行程排好了，你看看右侧预览。哪里不顺直接说，我再改。"

async def build_feedback_question(last_feedback:Optional[str],trip_plan:Optional[dict]) -> str:
    """用模型根据上一轮用户反馈生成自然追问；失败时不阻断对话。"""
    feedback = (last_feedback or "").strip()
    plan_summary = summarize_plan_for_feedback(trip_plan)
    logger.info("[Feedback] LLM 看到的真实行程:\n%s", plan_summary)
    system_prompt = (
        "你是旅行规划产品里的中文对话助手。"
        "根据用户上一轮反馈，生成一句自然的确认，告诉用户可以看右侧预览。"
        "要求：口语化，不要模板腔；不要说'行程已生成'；"
        "【严禁提及任何具体景点名或地名】——去了哪由右侧预览展示，你只做概括性确认；"
        "不要列举例子；"
    )

    user_prompt = (
        f"用户上一轮反馈：{feedback or '无，这是首次生成行程'}\n\n"
        f"当前行程摘要：\n{plan_summary}\n\n"
        "请直接输出要展示给用户的话。"
    )

    try:
        response = await feedback_llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
    except Exception:
        logger.exception("[Feedback] 生成反馈提示失败")
        return fallback_feedback_question(last_feedback)

    content = (getattr(response,"content","") or "").strip()
    logger.info("[Feedback] LLM 生成的追问:%s", content)
    return content or fallback_feedback_question(last_feedback)

async def clarify_node(state:ConversationState) -> dict:
    """检查规划前需澄清的问题"""
    req = state["request"]
    updates: dict = {}

    # 校验时间
    if req.start_date < date.today():
        user_answer: str = interrupt({
            "type":"clarify_date",
            "question":(
                f"行程时间不在未来，来规划{req.destination}{req.trip_days}天的行程。"
                
            )
        })
        new_date = datetime.strptime(user_answer.strip(),"%Y-%m-%d").date()
        new_req = TripRequest.model_validate(
            {**req.model_dump(), "start_date": new_date}
        )
        req = new_req
        updates["request"] = new_req

    # 意图识别
    intent = state["intent"]
    current_intent = intent
    conflicts = find_visit_conflicts(intent)
    for place in conflicts:
        question = (
            f"你对“{place}”的要求有冲突：既想去又想避开。"
            "请回复“去”或“不去”。"
        )
        decision = None
        while decision is None:
            answer: str= interrupt({
                "type":"clarify_visit_conflict",
                "place":place,
                "question":question
            })
            decision=parse_visit_decision(answer)
            if decision is None:
                question = (
                    f"我没理解你对“{place}”的决定。"
                    "请明确回复“去”或“不去”。"
                )
        current_intent = resolve_visit_conflict(
            intent=current_intent,
            place=place,
            decision=decision
        )

    if find_budget_ambiguities(current_intent):
        question = (
            "请确认预算口径，并尽量直接给出全程总预算金额，"
            "例如“全程总预算 3000 元”；如果是每日预算，也可以回复“每天 1000 元”。"
        )
        resolved_intent = None
        while resolved_intent is None:
            answer: str = interrupt({
                "type": "clarify_budget",
                "question": question,
                "ambiguities": find_budget_ambiguities(current_intent),
            })
            resolved_intent = resolve_budget_answer(
                current_intent,
                answer,
                req.trip_days,
            )
            if resolved_intent is None:
                question = "我还无法换算全程总预算，请直接回复如“全程总预算 3000 元”。"
        current_intent = resolved_intent

    remaining_ambiguities = [
        item
        for item in current_intent.ambiguities
        if "预算" not in item and "同时出现在必去和不想去" not in item
    ]
    if remaining_ambiguities:
        answer: str = interrupt({
            "type": "clarify_intent",
            "question": (
                "还有几项要求会明显影响规划，请补充说明："
                + "；".join(remaining_ambiguities)
            ),
            "ambiguities": remaining_ambiguities,
        })
        clarification_request = req.model_copy(
            update={"extra_requirements": answer.strip()}
        )
        clarification = await parse_travel_intent(clarification_request)
        current_intent = merge_travel_intents(current_intent, clarification)
        data = current_intent.model_dump()
        data["ambiguities"] = [
            item for item in data["ambiguities"] if item not in remaining_ambiguities
        ]
        current_intent = TravelIntent.model_validate(data)

    if current_intent != intent:
        updates["intent"] = current_intent
    return updates

async def plan_node(state:ConversationState,config:RunnableConfig) -> dict:
    logger.debug("plan_node 收到的 request: %s", state["request"])
    # 从config取运行时上下文里的user_id(RAG检索要用),取不到给空串
    user_id = config.get("configurable",{}).get("user_id","")
    result = await run_workflow(state["request"],intent=state["intent"],config=config,user_id=user_id)
    session = get_session()
    logger.debug("Phase1 收集到的景点数量: %d", len(session.get("attractions", [])))
    return {
        "trip_plan":result.get("trip_plan"),
        "raw_attractions":session.get("attractions",[]),
        "raw_hotels":session.get("hotels",[]),
        "token_used": result.get("token_used",0)    
    }

async def feedback_node(state:ConversationState) -> dict:
    """展示当前行程，等用户反馈（或'满意'结束）。"""
    answer = state.get("feedback_answer")
    note = state.get("revise_note")
    if answer:
        question = f"{answer}\n还有哪里想了解或调整吗？"
    elif note:
        # revise没成功：直接如实告知，绝不让LLM粉饰成“改好了”
        question = f"{note}\n换个说法或说得更具体些，我再试试。"
    else:
        # 正常情况
        question = await build_feedback_question(state.get("last_feedback"),state.get("trip_plan"))
    feedback: str = interrupt({
        "type":"feedback",
        "question":question,
        "trip_plan":state["trip_plan"]
    })
    # 清除note，避免残留到下一轮
    return {
        "last_feedback":feedback,
        "revise_note":None,
        "feedback_answer":None,
        "feedback_intent":None,
    }


async def classify_feedback_node(state: ConversationState) -> dict:
    classified = await classify_feedback(state.get("last_feedback") or "")
    return {"feedback_intent": classified}


def route_feedback(state: ConversationState) -> str:
    classified = state.get("feedback_intent")
    return classified.action if classified is not None else "unknown"

def should_revise(state:ConversationState) -> str:
    """条件边：路由到revise或END。"""
    feedback = (state.get("last_feedback") or "").strip().lower()
    done_words = {"满意","ok","可以","没问题","完成","done","结束","好"}
    if feedback in done_words:
        return END
    return "revise"


async def answer_question_node(state: ConversationState) -> dict:
    plan_summary = summarize_plan_for_feedback(state.get("trip_plan"))
    question = state.get("last_feedback") or ""
    try:
        response = await feedback_llm.ainvoke(
            [
                SystemMessage(content=(
                    "你负责回答用户对当前旅行计划的简短问题。只依据给出的行程摘要回答；"
                    "信息不足时如实说明，不修改行程，也不要声称已经修改。"
                )),
                HumanMessage(content=f"当前行程：\n{plan_summary}\n\n用户问题：{question}"),
            ]
        )
        answer = (getattr(response, "content", "") or "").strip()
    except Exception:
        logger.exception("[Feedback] 回答问题失败")
        answer = "暂时无法回答这个问题，你可以换个说法再问一次。"
    return {"feedback_answer": answer or "当前信息不足，暂时无法确认。"}


def unknown_feedback_node(state: ConversationState) -> dict:
    return {"revise_note": "我还不能确定你是想结束、提问还是修改行程。"}

async def revise_node(state:ConversationState) -> dict:
    """根据反馈调用修改工具"""
    feedback_request = state["request"].model_copy(
        update={"extra_requirements": state["last_feedback"]}
    )
    feedback_update = await parse_travel_intent(feedback_request)
    merged_intent = merge_travel_intents(state["intent"], feedback_update)
    new_plan,tokens,note = await apply_revision(
        feedback=state["last_feedback"],
        current_plan=state["trip_plan"],
        raw_attractions=state["raw_attractions"],
        raw_hotels=state["raw_hotels"],
        transport=state["request"].transport,
        intent=merged_intent,
    )
    merged_intent = get_revision_context().get("intent", merged_intent)
    repaired_plan = remove_cross_day_duplicates(new_plan)
    validation = validate_plan(repaired_plan, merged_intent)
    if not validation.passed:
        note = "这次修改会破坏已有约束，已保留原计划：" + "；".join(
            validation.violations
        )
        repaired_plan = state["trip_plan"]
    return {
        "trip_plan": repaired_plan,
        "intent": merged_intent,
        "token_used": state.get("token_used", 0) + tokens,
        "revise_note": note,
    }

def build_conversation_builder() -> StateGraph:
    """返回未 compile的 builder。compile放在main.py的lifespan里做，因为要注入checkpointer."""
    builder = StateGraph(ConversationState)

    builder.add_node("intent",intent_node)
    builder.add_node("clarify",clarify_node)
    builder.add_node("plan",plan_node)
    builder.add_node("feedback",feedback_node)
    builder.add_node("classify_feedback", classify_feedback_node)
    builder.add_node("revise",revise_node)
    builder.add_node("question", answer_question_node)
    builder.add_node("unknown_feedback", unknown_feedback_node)

    builder.add_edge(START,"intent")
    builder.add_edge("intent","clarify")
    builder.add_edge("clarify","plan")
    builder.add_edge("plan","feedback")
    builder.add_edge("feedback", "classify_feedback")
    builder.add_conditional_edges(
        "classify_feedback",
        route_feedback,
        {
            "finish": END,
            "revise": "revise",
            "question": "question",
            "unknown": "unknown_feedback",
        },
    )
    builder.add_edge("revise","feedback")
    builder.add_edge("question", "feedback")
    builder.add_edge("unknown_feedback", "feedback")

    return builder

if __name__ == "__main__":
    from IPython.display import Image,display
    res = build_conversation_builder().compile()
    png_bytes = res.get_graph().draw_mermaid_png()

    with open("graph.png", "wb") as f:
        f.write(png_bytes)
