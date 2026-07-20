"""
对话式行程规划的图。

流程：
    START -> clarify (可能interrupt) -> plan -> feedback(interrupt)
    feedback -> [满意] -> END
    feedback -> [想改] -> revise -> feedback(循环)
"""

import logging
from typing import TypedDict,Optional
from app.schemas import TripRequest,Attraction,Hotel
from langgraph.types import interrupt
from app.graph.workflow import run_workflow
from langgraph.graph import StateGraph,START,END
from app.agents.tools import get_session
from app.agents.revise_tools import apply_revision
from datetime import date,datetime
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import SystemMessage,HumanMessage
from langchain_deepseek import ChatDeepSeek

logger = logging.getLogger(__name__)

feedback_llm = ChatDeepSeek(model="deepseek-chat",temperature=0.6)

# 整个图的共享状态
class ConversationState(TypedDict):
    request: TripRequest
    trip_plan: Optional[dict]
    raw_attractions:list[Attraction]
    raw_hotels:list[Hotel]
    last_feedback:Optional[str]
    token_used: int

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

    system_prompt = (
        "你是旅行规划产品里的中文对话助手。"
        "根据用户上一轮反馈和当前行程状态，生成一句自然、具体的确认/追问。"
        "要求：口语化，不要模板腔；不要说'行程已生成'；不要列举例子；"
        "不要解释你做了什么工具调用；最多2句，总字数不超过70个中文字符；"
        "不要要求用户回复固定口令，例如'满意'或'done'。"
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
    return content or fallback_feedback_question(last_feedback)

async def clarify_node(state:ConversationState) -> dict:
    """若用户表单里 preferences为空，interrupt问一句。有值直接放行。"""
    req = state["request"]

    # 校验时间
    if req.start_date < date.today():
        user_answer: str = interrupt({
            "type":"clarify_date",
            "question":(
                f"行程时间不在未来，来规划{req.destination}{req.trip_days}天的行程。"
                
            )
        })
        new_date = datetime.strptime(user_answer.strip(),"%Y-%m-%d").date()
        new_req = req.model_copy(update={"start_date":new_date})
        return {"request":new_req}
    
    if req.preferences:
        return {}
    
    # 暂停图，把这个dict返回HTTP层
    user_answer: str = interrupt({
        "type":"clarify_preferences",
        "question":(
            f"好的，来规划{req.destination}{req.trip_days}天的行程。"
            f"你对景点有什么偏好？比如：历史文化/自然风光/美食/购物，"
            f"可选多个用逗号分隔"
        )
    })

    # user_answer是调用方 用Command(resume=...)传回来的字符串
    prefs = [p.strip() for p in user_answer.replace("，",",").split(",") if p.strip()]
    new_req = req.model_copy(update={"preferences":prefs})
    return {"request":new_req}

async def plan_node(state:ConversationState,config:RunnableConfig) -> dict:
    logger.debug("plan_node 收到的 request: %s", state["request"])
    # 从config取运行时上下文里的user_id(RAG检索要用),取不到给空串
    user_id = config.get("configurable",{}).get("user_id","")
    result = await run_workflow(state["request"],config=config,user_id=user_id)
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
    feedback: str = interrupt({
        "type":"feedback",
        "question":await build_feedback_question(state.get("last_feedback"),state.get("trip_plan")),
        "trip_plan":state["trip_plan"]
    })
    return {"last_feedback":feedback}

def should_revise(state:ConversationState) -> str:
    """条件边：路由到revise或END。"""
    feedback = (state.get("last_feedback") or "").strip().lower()
    done_words = {"满意","ok","可以","没问题","完成","done","结束","好"}
    if feedback in done_words:
        return END
    return "revise"

async def revise_node(state:ConversationState) -> dict:
    """根据反馈调用修改工具"""
    new_plan,tokens = await apply_revision(
        feedback=state["last_feedback"],
        current_plan=state["trip_plan"],
        raw_attractions=state["raw_attractions"],
        raw_hotels=state["raw_hotels"],
        transport=state["request"].transport
    )
    return {"trip_plan":new_plan,"token_used":tokens}

def build_conversation_builder() -> StateGraph:
    """返回未 compile的 builder。compile放在main.py的lifespan里做，因为要注入checkpointer."""
    builder = StateGraph(ConversationState)

    builder.add_node("clarify",clarify_node)
    builder.add_node("plan",plan_node)
    builder.add_node("feedback",feedback_node)
    builder.add_node("revise",revise_node)

    builder.add_edge(START,"clarify")
    builder.add_edge("clarify","plan")
    builder.add_edge("plan","feedback")
    builder.add_conditional_edges(
        "feedback",
        should_revise,
        {"revise":"revise",END:END}
    )
    builder.add_edge("revise","feedback")

    return builder

if __name__ == "__main__":
    from IPython.display import Image,display
    res = build_conversation_builder().compile()
    png_bytes = res.get_graph().draw_mermaid_png()

    with open("graph.png", "wb") as f:
        f.write(png_bytes)
