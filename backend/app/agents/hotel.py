"""
酒店agent:按用户住宿偏好查高德POI（类型=住宿服务）。
高德的住宿POI分类代码：
- 100101 五星级
- 100102 四星级
- 100103 三星级
- 100104 二星级及以下
- 100105 家庭旅馆/民宿
"""

import os
import requests
from dotenv import load_dotenv
from app.graph.state import TravelState
from app.schemas import Hotel

load_dotenv()

API_KEY = os.getenv("GAODE_API_KEY")

# 用户表单的住宿偏好 -> 高德POI 类型代码
ACCOMMODATION_TYPE_MAP= {
    "经济型酒店": "100103|100104",
    "舒适型酒店": "100102",
    "豪华型酒店": "100101",
    "民宿": "100105",
}

# 各个档次的粗略价格区间，直接写死 -- LLM不擅长估价
PRICE_RANGE_MAP= {
    "经济型酒店": "300-500元",
    "舒适型酒店": "500-900元",
    "豪华型酒店": "900-2000元",
    "民宿": "200-600元",
}

def fetch_hotels(city:str,hotel_type:str,limit:int = 5) -> list[dict]:
    url = "https://restapi.amap.com/v5/place/text"
    params = {
        "key":API_KEY,
        "types":ACCOMMODATION_TYPE_MAP.get(hotel_type,"100100"),
        "region":city,
        "city_limit":"true",
        "page_size":limit,
        "page_num":1,
        "show_fields":"business"
    }
    resp = requests.get(url,params=params,timeout=10)
    data = resp.json()
    if data.get("status") != "1":
        return []
    return data.get("pois",[])

def parse_to_hotel(poi:dict,hotel_type:str) -> Hotel:
    """高德POI -> Hotel schema。评分字段可能是空字符串，要兜底。"""
    rating_raw = (poi.get("business") or {}).get("rating","")
    try:
        rating = float(rating_raw) if rating_raw else 0.0
    except (ValueError,TypeError):
        rating = 0.0
    
    return Hotel(
        name=poi.get("name",""),
        address=poi.get("address") or poi.get("pname",""),
        type=hotel_type,
        price_range=PRICE_RANGE_MAP.get(hotel_type,"300-500元"),
        rating=rating,
        distance_note="距离景点5公里" # 简化处理：精确距离可以后面迭代
    )

def hotel_node(state:TravelState) -> dict:
    req = state["request"]
    print(f"[HotelAgent]查询{req.destination}的{req.accommodation}")

    try:
        pois = fetch_hotels(req.destination,req.accommodation,limit=5)
        hotels = [parse_to_hotel(p,req.accommodation) for p in pois]
        print(f"[HotelAgent]找到{len(hotels)}家酒店")
    except Exception as e:
        print(f"[HotelAgent]查询失败：{e}")
        hotels = []
    
    return {"hotels_raw":hotels}

