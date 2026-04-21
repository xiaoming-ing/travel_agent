from typing import TypedDict,Annotated,List,Optional
from app.schemas import TripRequest,Attraction,Hotel

RESET = {"__reset__": True}  # 哨兵值

def merge_dict(a:dict,b:dict) -> dict:
    return {**(a or {}),**(b or {})}

class TravelState(TypedDict):
    # 入口写入，其他节点只读
    request: TripRequest

    # 三个数据源agent写入
    weather_raw:List[dict]
    attractions_raw:List[Attraction]
    hotels_raw:List[Hotel]

    # 合成agent写入最终结果
    trip_plan:dict