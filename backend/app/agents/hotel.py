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
import math
import requests
from dotenv import load_dotenv
from app.graph.state import TravelState
from app.schemas import Hotel, Attraction

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

# 按交通方式的打分权重 (w_rating, w_distance, max_km) 评分权重，距离权重，能接受的最远距离
TRANSPORT_WEIGHTS = {
    "公共交通": (0.6, 0.4, 8.0),
    "自驾":     (0.4, 0.6, 6.0),
    "打车":     (0.4, 0.6, 6.0),
    "步行":     (0.2, 0.8, 3.0),
}
DEFAULT_WEIGHTS = (0.5, 0.5, 8.0)


def compute_centroid(attractions: list[Attraction]) -> tuple[float, float] | None:
    """返回景点几何重心 (lng, lat)。空列表返回 None。"""
    if not attractions:
        return None
    n = len(attractions)
    return (
        sum(loc.longitude for loc in attractions) / n,
        sum(loc.latitude for loc in attractions) / n
    )


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """两点经纬度之间的公里距离。"""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def score_hotel(rating: float, distance_km: float, transport: str) -> float:
    """按交通方式给酒店打分，分越高越优。"""
    w_rating, w_distance, max_km = TRANSPORT_WEIGHTS.get(transport,DEFAULT_WEIGHTS)
    rating_score = rating / 5.0
    distance_score = max(0, 1 - distance_km / max_km)
    return w_rating * rating_score + w_distance * distance_score


def fetch_hotels_around(centroid: tuple[float, float], hotel_type: str, limit: int = 15) -> list[dict]:
    """以景点重心为圆心做周边搜，返回高德 POI 原始 dict 列表。"""
    lng, lat = centroid
    url = "https://restapi.amap.com/v5/place/around"
    params = {
        "key": API_KEY,
        "location": f"{lng},{lat}",
        "radius": 10000,
        "types": ACCOMMODATION_TYPE_MAP.get(hotel_type, "100100"),
        "page_size": limit,
        "page_num": 1,
        "show_fields": "business",
        "sortrule": "weight",
    }
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()
    if data.get("status") != "1":
        return []
    return data.get("pois", [])


def fetch_hotels_by_city(city: str, hotel_type: str, limit: int = 5) -> list[dict]:
    """退化路径：景点重心算不出来时，按城市全市搜（保留旧行为）。"""
    url = "https://restapi.amap.com/v5/place/text"
    params = {
        "key": API_KEY,
        "types": ACCOMMODATION_TYPE_MAP.get(hotel_type, "100100"),
        "region": city,
        "city_limit": "true",
        "page_size": limit,
        "page_num": 1,
        "show_fields": "business",
    }
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()
    if data.get("status") != "1":
        return []
    return data.get("pois", [])


def parse_to_hotel(poi: dict, hotel_type: str) -> Hotel | None:
    """高德 POI -> Hotel schema。location 缺失返回 None。"""
    loc = poi.get("location", "")
    if not loc or "," not in loc:
        return None
    try:
        lng, lat = (float(x) for x in loc.split(","))
    except ValueError:
        return None

    rating_raw = (poi.get("business") or {}).get("rating", "")
    try:
        rating = float(rating_raw) if rating_raw else 0.0
    except (ValueError, TypeError):
        rating = 0.0

    return Hotel(
        name=poi.get("name", ""),
        address=poi.get("address") or poi.get("pname", ""),
        type=hotel_type,
        price_range=PRICE_RANGE_MAP.get(hotel_type, "300-500元"),
        rating=rating,
        distance_note="",                      # hotel_node 里再填
        longitude=lng,
        latitude=lat,
    )

def hotel_node(state: TravelState) -> dict:
    req = state["request"]
    attractions = state.get("attractions_raw", [])
    print(f"[HotelAgent] 查询 {req.destination} 的 {req.accommodation}（候选景点 {len(attractions)} 个）")

    centroid = compute_centroid(attractions)

    try:
        if centroid is None:
            print("[HotelAgent] 无景点重心，退回按城市搜")
            pois = fetch_hotels_by_city(req.destination, req.accommodation, limit=5)
            hotels = [h for h in (parse_to_hotel(p, req.accommodation) for p in pois) if h]
            return {"hotels_raw": hotels}

        pois = fetch_hotels_around(centroid, req.accommodation, limit=15)
        hotels = [h for h in (parse_to_hotel(p, req.accommodation) for p in pois) if h]

        centroid_lng, centroid_lat = centroid
        scored: list[tuple[float, Hotel]] = []
        for h in hotels:
            d = haversine(h.latitude, h.longitude, centroid_lat, centroid_lng)
            h.distance_note = f"距景点中心 {d:.1f}km"
            s = score_hotel(h.rating, d, req.transport)
            scored.append((s, h))

        scored.sort(key=lambda x: x[0], reverse=True)
        sorted_hotels = [h for _, h in scored]
        if sorted_hotels:
            top = sorted_hotels[0]
            print(f"[HotelAgent] 共 {len(sorted_hotels)} 家，最优：{top.name}（{top.distance_note}, 评分 {top.rating}）")
        else:
            print("[HotelAgent] 周边无可用酒店")
        return {"hotels_raw": sorted_hotels}

    except Exception as e:
        print(f"[HotelAgent] 查询失败：{e}")
        return {"hotels_raw": []}


if __name__ == "__main__":
    # 1. compute_centroid
    a1 = Attraction(name="x", address="", longitude=116.0, latitude=39.0,
                    duration_minutes=0, ticket_price=0, description="")
    a2 = Attraction(name="y", address="", longitude=116.4, latitude=39.4,
                    duration_minutes=0, ticket_price=0, description="")
    lng, lat = compute_centroid([a1, a2])
    assert abs(lng - 116.2) < 1e-6 and abs(lat - 39.2) < 1e-6, (lng, lat)
    assert compute_centroid([]) is None

    # 2. haversine：北京天安门(116.40,39.90) <-> 故宫(116.40,39.92) 约 2.2km
    d = haversine(39.90, 116.40, 39.92, 116.40)
    assert 2.0 < d < 2.5, d

    # 3. score_hotel
    s_high = score_hotel(4.5, 2.0, "公共交通")
    s_low  = score_hotel(3.0, 2.0, "公共交通")
    assert s_high > s_low, (s_high, s_low)
    s_near_drive = score_hotel(4.0, 1.0, "自驾")
    s_far_drive  = score_hotel(4.0, 5.0, "自驾")
    assert s_near_drive > s_far_drive
    score_hotel(4.0, 2.0, "热气球")  # 未知 transport 走 DEFAULT_WEIGHTS

    print("[hotel.py self-check] OK")
