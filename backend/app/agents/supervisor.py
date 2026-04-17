from langchain_deepseek import ChatDeepSeek
from app.graph.state import TravelState
from langchain_core.messages import SystemMessage,HumanMessage,AIMessage
from pydantic import BaseModel,Field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Supervisor的系统提示词

SUPERVISOR_PROMPT = """你是一个旅行助手的入口调度员。
你的唯一职责：从用户对话中提取三项信息，不齐就追问。
- 目的地（destination）
- 出行日期（dates）
- 预算（budget）

当前已收集到的信息：
- 目的地：{destination}
- 日期： {dates}
- 预算：{budget}

规则：
-  一次只追问1-2个缺失信息，不要一口气全问
- 语气友好自然，像朋友聊天
- 如果用户本轮提供了新信息，把它提取出来
- 用户提供的信息可能分散在多轮对话中，注意累积提取
- 信息已全部齐全时，response 可以简短说一句"好的，我来帮你查一下"，不要自己编行程建议——后面有专门的节点负责
"""


class SupervisorOutput(BaseModel):
    """Supervisor结构化输出"""
    response:str = Field(description="回复给用户的文本")
    destination:Optional[str] = Field(description="提取到的目的地，没有则为null",default=None)
    dates:Optional[dict] = Field(description="提取到的日期，没有则为null",default=None)
    budget:Optional[float] = Field(description="提取到的预算金额，没有则为null",default=None)
    info_compelete: bool = Field(description="三项信息是否已全部收集齐",default=None)

llm = ChatDeepSeek(model="deepseek-chat",temperature=0)
structured_llm = llm.with_structured_output(SupervisorOutput)

def surpervisor_node(state:TravelState) -> dict:
    """Supervisor节点：提取信息+追问确认"""
    destination = state.get("destination","未知")
    dates = state.get("dates","未知")
    budget = state.get("budget","未知")
    # 拼装当前已有信息到提示词
    prompt = SUPERVISOR_PROMPT.format(
        destination=destination,
        dates=dates,
        budget=budget,
        agent_outputs=state.get("agent_outputs",None)
    )

    messages = [SystemMessage(content=prompt)] + state["messages"]
    result = structured_llm.invoke(messages)

    updates = {"messages":[AIMessage(content=result.response)]}

    if result.destination:
        updates["destination"] = result.destination
    if result.dates:
        updates["dates"] = result.dates
    if result.budget:
        updates["budget"] = result.budget

    return updates
# 后续，给给 Supervisor 绑一个 extract_info 工具，
