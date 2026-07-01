"""从LangChain 消息里提取真实token消耗。"""

from langchain_core.messages import AIMessage

def count_tokens(messages:list) -> int:
    """把一串消息里所有AIMEssage的usage_metadata.total_tokens加起来。
    某些异常情况下usage_metadata可能缺失，按0算，不阻塞主流程。
    """
    total = 0
    for m in messages:
        if isinstance(m,AIMessage) and m.usage_metadata:
            total += m.usage_metadata.get("total_tokens",0) or 0
    return total
