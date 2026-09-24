import logging
from datetime import date, datetime

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from app.conversation.clarification import (
    find_budget_ambiguities,
    find_visit_conflicts,
    merge_travel_intents,
    parse_visit_decision,
    resolve_budget_answer,
    resolve_visit_conflict,
)
from app.conversation.feedback import (
    build_feedback_question,
    classify_feedback,
    feedback_llm,
    summarize_plan_for_feedback,
)
from app.conversation.state import ConversationState
from app.db.preferences_store import get_preferences
from app.planning.collection_tools import get_session
from app.planning.intent_parser import parse_travel_intent
from app.planning.service import run_workflow
from app.planning.validator import remove_cross_day_duplicates, validate_plan
from app.revision.agent import apply_revision
from app.revision.context import get_ctx as get_revision_context
from app.schemas import TravelIntent, TripRequest

logger = logging.getLogger(__name__)


async def intent_node(state: ConversationState, config: RunnableConfig) -> dict:
    request = state["request"]
    user_id = config.get("configurable", {}).get("user_id", "")
    saved_preferences = None
    if user_id:
        try:
            saved_preferences = await get_preferences(user_id)
        except Exception:
            logger.exception("[Intent] 读取长期偏好失败，继续使用本次请求")
    intent = await parse_travel_intent(request, saved_preferences=saved_preferences)
    return {"intent": intent}


async def clarify_node(state: ConversationState) -> dict:
    """检查规划前需澄清的问题。"""
    request = state["request"]
    updates: dict = {}

    if request.start_date < date.today():
        user_answer: str = interrupt(
            {
                "type": "clarify_date",
                "question": f"行程时间不在未来，来规划{request.destination}{request.trip_days}天的行程。",
            }
        )
        new_date = datetime.strptime(user_answer.strip(), "%Y-%m-%d").date()
        request = TripRequest.model_validate(
            {**request.model_dump(), "start_date": new_date}
        )
        updates["request"] = request

    intent = state["intent"]
    current_intent = intent
    for place in find_visit_conflicts(intent):
        question = (
            f"你对“{place}”的要求有冲突：既想去又想避开。"
            "请回复“去”或“不去”。"
        )
        decision = None
        while decision is None:
            answer: str = interrupt(
                {
                    "type": "clarify_visit_conflict",
                    "place": place,
                    "question": question,
                }
            )
            decision = parse_visit_decision(answer)
            if decision is None:
                question = f"我没理解你对“{place}”的决定。请明确回复“去”或“不去”。"
        current_intent = resolve_visit_conflict(current_intent, place, decision)

    if find_budget_ambiguities(current_intent):
        question = (
            "请确认预算口径，并尽量直接给出全程总预算金额，"
            "例如“全程总预算 3000 元”；如果是每日预算，也可以回复“每天 1000 元”。"
        )
        resolved_intent = None
        while resolved_intent is None:
            answer = interrupt(
                {
                    "type": "clarify_budget",
                    "question": question,
                    "ambiguities": find_budget_ambiguities(current_intent),
                }
            )
            resolved_intent = resolve_budget_answer(
                current_intent, answer, request.trip_days
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
        answer = interrupt(
            {
                "type": "clarify_intent",
                "question": "还有几项要求会明显影响规划，请补充说明："
                + "；".join(remaining_ambiguities),
                "ambiguities": remaining_ambiguities,
            }
        )
        clarification_request = request.model_copy(
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


async def plan_node(state: ConversationState, config: RunnableConfig) -> dict:
    logger.debug("plan_node 收到的 request: %s", state["request"])
    user_id = config.get("configurable", {}).get("user_id", "")
    result = await run_workflow(
        state["request"], intent=state["intent"], config=config, user_id=user_id
    )
    session = get_session()
    logger.debug("Phase1 收集到的景点数量: %d", len(session.get("attractions", [])))
    return {
        "trip_plan": result.get("trip_plan"),
        "raw_attractions": session.get("attractions", []),
        "raw_hotels": session.get("hotels", []),
        "token_used": result.get("token_used", 0),
    }


async def feedback_node(state: ConversationState) -> dict:
    answer = state.get("feedback_answer")
    note = state.get("revise_note")
    if answer:
        question = f"{answer}\n还有哪里想了解或调整吗？"
    elif note:
        question = f"{note}\n换个说法或说得更具体些，我再试试。"
    else:
        question = await build_feedback_question(
            state.get("last_feedback"), state.get("trip_plan")
        )
    feedback: str = interrupt(
        {"type": "feedback", "question": question, "trip_plan": state["trip_plan"]}
    )
    return {
        "last_feedback": feedback,
        "revise_note": None,
        "feedback_answer": None,
        "feedback_intent": None,
    }


async def classify_feedback_node(state: ConversationState) -> dict:
    classified = await classify_feedback(state.get("last_feedback") or "")
    return {"feedback_intent": classified}


def route_feedback(state: ConversationState) -> str:
    classified = state.get("feedback_intent")
    return classified.action if classified is not None else "unknown"


async def answer_question_node(state: ConversationState) -> dict:
    plan_summary = summarize_plan_for_feedback(state.get("trip_plan"))
    question = state.get("last_feedback") or ""
    try:
        response = await feedback_llm.ainvoke(
            [
                SystemMessage(
                    content=(
                        "你负责回答用户对当前旅行计划的简短问题。只依据给出的行程摘要回答；"
                        "信息不足时如实说明，不修改行程，也不要声称已经修改。"
                    )
                ),
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


async def revise_node(state: ConversationState) -> dict:
    feedback_request = state["request"].model_copy(
        update={"extra_requirements": state["last_feedback"]}
    )
    feedback_update = await parse_travel_intent(feedback_request)
    merged_intent = merge_travel_intents(state["intent"], feedback_update)
    new_plan, tokens, note = await apply_revision(
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
