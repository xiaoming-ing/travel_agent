from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from app.graph.state import TravelState,RESET
from langchain_core.messages import SystemMessage,AIMessage


load_dotenv()

SUMMARIZER_PROMPT = """你是一位资深旅行规划师，要把各位专家的分析整合成最终建议。

用户信息：
- 目的地：{destination}
- 日期： {dates}
- 预算：{budget}元

各专家的分析：
{sections}

请用朋友聊天的语气整合成一份连贯的建议（250字左右）
1.开头点名整体感觉（天气合不合适、值不值得去）
2.自然窜联个方面要点，不要分段罗列
3.结尾给一个具体的行动建议
不要出现“天气专家说”“景点专家说”这种机械表述。
"""

LABEL_MAP = {
    "weather":"【天气】",
    "attraction":"【景点】",
}

llm = ChatDeepSeek(model="deepseek-chat",temperature=0.6)

def summarizer_node(state:TravelState) -> dict:
    outputs = state.get("agent_outputs",{})

    sections = "\n\n".join(
        f"{LABEL_MAP.get(k,k)}\n{v}" for k,v in outputs.items()
    )

    prompt = SUMMARIZER_PROMPT.format(
        destination=state.get("destination", ""),
        dates=state.get("dates", {}),
        budget=state.get("budget", 0),
        sections=sections
    )

    print("[Summarizer]汇总中。。。")
    result = llm.invoke([SystemMessage(content=prompt)])

    return {
        "messages":[AIMessage(content=result.content)],
        "agent_outputs":RESET # 清空，避免下一轮污染
    }

