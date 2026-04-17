from langgraph.graph import StateGraph,START,END
from app.agents.supervisor import surpervisor_node
from app.graph.state import TravelState
from langgraph.checkpoint.memory import MemorySaver
from app.agents.weather import weather_node
from app.agents.attraction import attraction_node
from app.agents.summarizer import summarizer_node
from IPython.display import Image,display
from langchain_core.messages import AIMessage

def should_continue(state:TravelState) -> str:
    """
    Supervisor之后的路由
    - 如果agent_outputs已有结果，说明这轮是“汇总回复，直接结束
    - 如果信息齐了单还没结果，派发天气Agent
    - 其他情况（信息不全）直接结束，等用户下一轮输入
    """
    dest = state.get("destination")
    dates = state.get("dates")
    budget = state.get("budget")

    # 分析师跑完-> 去汇总
    if state.get("agent_outputs"):
        return "summarize"
    # 信息齐全 → 派活给分析师们（并行）
    if dest and dates and budget:
        return ["weather","attraction"]
    # 信息不全，等瀛湖下一轮输入
    return "need_more"



builder = StateGraph(TravelState)

builder.add_node("supervisor",surpervisor_node)
builder.add_node("weather",weather_node)
builder.add_node("attraction",attraction_node)
builder.add_node("summarizer", summarizer_node)

builder.add_edge(START,"supervisor")
builder.add_conditional_edges(
    "supervisor",
    should_continue,
    {
        "weather":"weather",
        "attraction":"attraction",
        "need_more":END,
        "summarize":"summarizer"
    }
)
# 分析师跑完，回supervisor,由should_continue路由到summarizer
builder.add_edge("weather","supervisor")
builder.add_edge("attraction","supervisor")

# 汇总完直接结束
builder.add_edge("summarizer",END)

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

if __name__ == "__main__":
    png_bytes = graph.get_graph().draw_mermaid_png()
    with open("workflow.png", "wb") as f:
        f.write(png_bytes)