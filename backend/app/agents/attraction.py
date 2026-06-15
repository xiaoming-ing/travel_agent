"""
景点agent:查高德POI ->输出结构化Attraction列表。
不做文字总结，只做数据采集。
文字描述/游览时长/门票等细节交给 intinerary agent统一生成。-- 职责更清晰
"""

import os
import requests
from dotenv import load_dotenv
from app.schemas import Attraction

load_dotenv()

API_KEY = os.getenv("GAODE_API_KEY")
PREFERENCE_POI_MAP = {
    "历史文化": ["110200","140100"], # 风景名胜子类（古迹/宗教）+ 博物馆
    "自然风光": ["110100", "110201"],  # 公园广场 + 国家级风景区
    "美食":    ["050100", "050200"],  # 中餐厅 + 外国餐厅
    "购物":    ["060100", "061000"],  # 商场 + 便民商店
    "艺术":    ["140200", "140400"],  # 展览馆 + 美术馆
    "休闲":    ["080100", "110100"],  # 体育休闲 + 公园
    "亲子":    ["060100","060900"], # 游乐园动物园
}
# 兜底：用户没选偏好时用这个
DEFAULT_POI_TYPES= "110000|140100"

def resolve_poi_types(preferences: list[str]) -> str:
    """用户偏好 → 高德 POI type 参数字符串。
    多个偏好取并集。没有偏好或都映射不上时走默认（风景名胜+博物馆）。"""
    if not preferences:
        return DEFAULT_POI_TYPES
    codes: set[str] = set()
    for p in preferences:
        codes.update(PREFERENCE_POI_MAP.get(p, []))
    if not codes:
        return DEFAULT_POI_TYPES
    return "|".join(sorted(codes))

def fetch_attractions(city:str,limit:int=10,types: str = DEFAULT_POI_TYPES,) -> list[dict]:
    """按城市搜索景点"""
    url = "https://restapi.amap.com/v5/place/text"
    params = {
        "key":API_KEY,
        "keywords":"景点",
        "types":types,
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
        ticket_price=0,
        description="",
        image_url=image_url
    )


def search_attraction_by_name(city: str, keyword: str) -> dict | None:
    """按用户给的名字在城市里精确查一个 POI。优先取完全同名，找不到取最相似的第一个。"""
    url = "https://restapi.amap.com/v5/place/text"
    params = {
        "key": API_KEY,
        "keywords": keyword,
        "region": city,
        "city_limit": "true",
        "page_size": 5,
        "page_num": 1,
        "show_fields": "business,photos",
    }
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()
    if data.get("status") != "1":
        return None
    pois = data.get("pois", [])
    # 优先完全同名
    for poi in pois:
        if poi.get("name") == keyword:
            return poi
    # 退而求其次取第一个模糊匹配
    return pois[0] if pois else None
