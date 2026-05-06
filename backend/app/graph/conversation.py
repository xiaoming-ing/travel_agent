"""
对话式行程规划的图。

流程：
    START -> clarify (可能interrupt) -> plan -> feedback(interrupt)
    feedback -> [满意] -> END
    feedback -> [想改] -> revise -> feedback(循环)
"""

from typing import TypedDict,Optional
from app.schemas import TripRequest,Attraction,Hotel
from langgraph.types import interrupt
from app.graph.workflow import run_workflow
from langgraph.graph import StateGraph,START,END
from app.agents.tools import get_session
from app.agents.revise_tools import apply_revision

class ConversationState(TypedDict):
    request: TripRequest
    trip_plan: Optional[dict]
    raw_attractions:list[Attraction]
    raw_hotels:list[Hotel]
    last_feedback:Optional[str]

async def clarify_node(state:ConversationState) -> dict:
    """若用户表单里 preferences为空，interrupt问一句。有值直接放行。"""
    req = state["request"]
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

async def plan_node(state:ConversationState) -> dict:
    result = await run_workflow(state["request"])
    session = get_session()
    return {
        "trip_plan":result.get("trip_plan"),
        "raw_attractions":session.get("attractions",[]),
        "raw_hotels":session.get("hotels",[])
    }

async def feedback_node(state:ConversationState) -> dict:
    """展示当前行程，等用户反馈（或'满意'结束）。"""
    feedback: str = interrupt({
        "type":"feedback",
        "question":(
            "行程已生成。有什么想调整的吗？\n"
            "例如：'Day 2的博物馆太多了，换成户外'、'酒店换成豪华型'\n"
            "输入'满意'或'done'结束对话"
        ),
        "trip_plan":state["trip_plan"]
    })
    return {"last_feedback":feedback}

def should_revise(state:ConversationState) -> str:
    """条件边：路由到revise或END。"""
    feedback = (state.get("last_feedback") or "").strip().lower()
    done_words = {"满意","ok","可以","没问题","完成","done","结束"}
    if feedback in done_words:
        return END
    return "revise"

async def revise_node(state:ConversationState) -> dict:
    """根据反馈调用修改工具"""
    new_plan = await apply_revision(
        feedback=state["last_feedback"],
        current_plan=state["trip_plan"],
        raw_attractions=state["raw_attractions"],
        raw_hotels=state["raw_hotels"],
        transport=state["request"].transport
    )
    return {"trip_plan":new_plan}

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