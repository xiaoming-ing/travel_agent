"""对话式行程规划图的拓扑定义。"""

from langgraph.graph import END, START, StateGraph

from app.conversation.nodes import (
    answer_question_node,
    clarify_node,
    classify_feedback_node,
    feedback_node,
    intent_node,
    plan_node,
    revise_node,
    route_feedback,
    unknown_feedback_node,
)
from app.conversation.state import ConversationState


def build_conversation_builder() -> StateGraph:
    """返回未编译的图；checkpointer 由应用启动过程注入。"""
    builder = StateGraph(ConversationState)

    builder.add_node("intent", intent_node)
    builder.add_node("clarify", clarify_node)
    builder.add_node("plan", plan_node)
    builder.add_node("feedback", feedback_node)
    builder.add_node("classify_feedback", classify_feedback_node)
    builder.add_node("revise", revise_node)
    builder.add_node("question", answer_question_node)
    builder.add_node("unknown_feedback", unknown_feedback_node)

    builder.add_edge(START, "intent")
    builder.add_edge("intent", "clarify")
    builder.add_edge("clarify", "plan")
    builder.add_edge("plan", "feedback")
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
    builder.add_edge("revise", "feedback")
    builder.add_edge("question", "feedback")
    builder.add_edge("unknown_feedback", "feedback")
    return builder
