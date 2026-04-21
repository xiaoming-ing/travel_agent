"""
景点agent:查高德POI ->输出结构化Attraction列表。
不做文字总结，只做数据采集。
文字描述/游览时长/门票等细节交给 intinerary agent统一生成。-- 职责更清晰
"""

import os
import requests
from dotenv import load_dotenv
from app.graph.state import TravelState
from app.schemas import Attraction

load_dotenv()

API_KEY = os.getenv("GAODE_API_KEY")
# 高德POI类型：110000=风景名胜，140000=科教文化（博物馆等）
POI_TYPES= "110000|140100"


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
        "show_fields":"business,photos" # 能拿到营业时间和评分,photos拿图片URL
    }
    resp = requests.get(url,params=params,timeout=10)
    data = resp.json()
    if data.get("status") != "1":
        return []

    return data.get("pois",[])
    
def parse_to_attraction(poi:dict) -> Attraction | None:
    """高德POI原始dict转化为Attraction schema.解析失败返回None"""
    loc = poi.get("location","")
    if not loc or "," not in loc:
        return None
    lng,lat = loc.split(",")

    # photos 字段是数组，可能为空
    photos = poi.get("photos") or []
    image_url = photos[0].get("url") if photos else None

    return Attraction(
        name=poi.get("name",""),
        address=poi.get("address") or poi.get("pname",""),
        longitude=float(lng),
        latitude=float(lat),
        # 下面三个字段高德不提供，先给默认值；itinerary agent 会基于名称补全
        duration_minutes=120,
        tricket_price=0,
        description="",
        image_url=image_url
    )

def attraction_node(state:TravelState) -> dict:
    """LangGraph节点。从state读request,返回要合并进state的字段"""
    req = state["request"]
    print(f"[AttractionAgent]查询{req.destination}的景点")

    try:
        pois = fetch_attractions(req.destination,limit=10)
        attractions: list[Attraction] = []
        for p in pois:
            a = parse_to_attraction(p)
            if a:
                attractions.append(a)
        print(f"[AttractionAgent]找到{len(attractions)}个景点")
    except Exception as e:
        print(f"[AttractionAgent]查询失败：{e}")
        attractions = []
    return {"attractions_raw": attractions}


# if __name__ == '__main__':
#     attraction_node({"destination":"北京","dates":{"days":3},"budget":5000}) 