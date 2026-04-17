from typing import TypedDict,Annotated,List,Optional
from langgraph.graph.message import add_messages

RESET = {"__reset__": True}  # 哨兵值

def merge_dict(a:dict,b:dict) -> dict:
    return {**(a or {}),**(b or {})}

class TravelState(TypedDict):
    messages:Annotated[List,add_messages]
    destination:str    # 目的地
    dates: dict       # 日期
    budget: float     # 预算
    weather_info: Optional[dict] # 天气agent输出
    agent_outputs:Annotated[dict,merge_dict] # 多个子agent并行执行获取状态

