import os
import requests
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import SystemMessage
from app.graph.state import TravelState

load_dotenv()

API_KEY = os.getenv("GAODE_API_KEY")
# 高德POI类型：110000=风景名胜，140000=科教文化（博物馆等）
POI_TYPES= "110000|140100"

ATTRACTION_ANALYST_PROMPT = """你是一个景点推荐官，熟悉各地的旅游资源。
用户要去{location}玩{trip_days}天。
以下是当地热门景点数据：
{attractions}

请用3-5句话推荐：
1.精选3-5个最值得去的（别全列）
2.说明每个的亮点（自然/文化/亲子/拍照等）
3.如果景点分布分散，可以提行程安排建议（比如“东城区一天够逛”）
像朋友推荐那样自然，不要罗列所有数据。
"""

llm = ChatDeepSeek(model="deepseek-chat",temperature=0.5)

def fetch_attractions(city:str,limit:int=10) -> list[dict]:
    """按城市搜索景点"""
    url = "https://restapi.amap.com/v5/place/text"
    params = {
        "key":API_KEY,
        "keywords":"景点",
        "types":POI_TYPES,
        "region":city,
        "city_limit":"true", # 限制只在该城市内搜
        "page_size":limit,
        "page_num":1,
        "show_fields":"business" # 能拿到营业时间和评分
    }
    resp = requests.get(url,params=params,timeout=10)
    data = resp.json()
    if data.get("status") != "1":
        return []

    return [
        {
            "name":p.get("name"),
            "address":p.get("address"), 
            "type":p.get("type"), # 类型，如“风景名胜；公园广场”
            "location":p.get("location"), # “经度，纬度”
            "rating":p.get("business",{}).get("rating"), # 评分，可能为空
            "tag":p.get("business",{}).get("tag")  # 特色内容
        }
        for p in data.get("pois",[])
    ]
    
async def summarize_attractions(info:dict) -> str:
    if info.get("error"):
        return f"景点查询失败:{info['error']}"
    prompt = ATTRACTION_ANALYST_PROMPT.format(
        location=info["location"],
        trip_days=info["trip_days"],
        attractions=info["attractions"]
    )

    result = await llm.ainvoke([SystemMessage(content=prompt)])
    return result.content

async def attraction_node(state:TravelState) -> dict:
    destination = state.get("destination","")
    dates = state.get("dates",{})
    trip_days = int(dates.get("days",3))

    print(f"[AttractionAgent] 查询{destination}的景点")

    try:
        attractions = fetch_attractions(destination,limit=10)
        if not attractions:
            info = {"location":destination,"error":"没有找到景点"}
        else:
            info = {
                "location":destination,
                "trip_days":trip_days,
                "attractions":attractions
            }
            print(f"[AttractionAgent] 找到{len(attractions)}个景点")
    except Exception as e:
        print(f"[AttractionAgent]查询失败:{e}")
        info = {"location":destination,"error":str(e)}
    
    summary = await summarize_attractions(info)
    return {"agent_outputs":{"attraction":summary}}

# if __name__ == '__main__':
#     attraction_node({"destination":"北京","dates":{"days":3},"budget":5000}) 