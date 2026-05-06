
from app.agents.weather import lookup_location_id,fetch_weather,pick_endpoint_days
from app.agents.attraction import fetch_attractions,parse_to_attraction,resolve_poi_types
from app.agents.hotel import fetch_hotels_around,parse_to_hotel,compute_centroid,haversine,score_hotel
from langchain_core.tools import tool
import contextvars


_session_var: contextvars.ContextVar[dict] = contextvars.ContextVar(
    'agent_session',
    default=None
)

def reset_session() -> None:
    _session_var.set({"attractions":[],"hotels":[],"weather":[]})


def get_session() -> dict:
    val = _session_var.get()
    if val is None:
        # 还没reset过，自动初始化（防御性）
        reset_session()
        return _session_var.get()
    return val


@tool
def search_attractions(city:str,preferences: list[str] = [],limit:int = 10) -> str:
    """搜索制定城市的景点（风景名胜+文化场所）。规划行程的第一步通常是调用此工具.
    Args:
        city:目的地城市名，例如“南京”，“上海”
        preferences: 用户偏好，影响搜到的地点类型。取值必须是以下之一：
                     "历史文化"/"自然风光"/"美食"/"购物"/"艺术"/"休闲"
                     传空列表走默认（风景名胜+博物馆）
        limit:返回数量上限，建议8～12
    
    Returns:
        景点摘要列表文本
    """
    types = resolve_poi_types(preferences)
    pois = fetch_attractions(city,limit=limit,types=types)
    attractions = [a for a in (parse_to_attraction(p) for p in pois) if a]
    session = get_session()
    session["attractions"] = attractions
    if not attractions:
        return f"未在{city}搜到景点，建议换个查询方式"
    lines = [f"-{a.name}({a.address})" for a in attractions]
    return (
        f"按偏好 {preferences or '默认（风景/博物馆）'} 找到 {len(attractions)} 个地点：\n"
        + "\n".join(lines)
    )

@tool
def get_weather(city:str,trip_days:int) -> str:
    """查询城市未来几天的天气预报，用于帮助用户做穿衣和出行建议。
    Args:
        city:城市名
        trip_days:用户实际出行天数；工具会自动获取和风天气支持的最近端点（3/7/10/15/30）

    Returns:
        每日天气摘要文本
    """
    loc_id = lookup_location_id(city)
    if not loc_id:
        return f"未找到城市{city}"
    days = pick_endpoint_days(trip_days)
    forecast = fetch_weather(loc_id,days=days)[:trip_days]
    session = get_session()
    session["weather"] = forecast
    if not forecast:
        return f"{city}天气查询失败"
    lines = [
        f"- {f['date']}: 白天{f['day_weather']}，夜间{f['night_weather']}，"
        f"{f['min_temp']}~{f['max_temp']}°C"
        for f in forecast
    ]
    return f"{city}未来{len(forecast)}天天气：\n" + "\n".join(lines)


@tool
def search_hotels(accommodation_type:str,transport:str="公共交通") -> str:
    """以已查到的景点几何重心为圆心搜周边酒店，按交通方式综合打分。
    必须先调用search_attractions 获取景点，否则算不出重心

    Args:
        accommodation_type:住宿档次，必须是"经济型酒店"/"舒适型酒店"/"豪华型酒店" / "民宿" 之一
        transport: 用户主要交通方式，可选 "公共交通"/"自驾"/"打车"/"步行"，影响打分权重

    Returns:
        综合打分后Top5酒店摘要
    """
    attractions = get_session().get("attractions",[])
    if not attractions:
        return "请先调用search_attractions获取景点，再调用此工具"
    
    centroid = compute_centroid(attractions)
    if centroid is None:
        return "景点经纬度无效，无法计算重心"
    pois = fetch_hotels_around(centroid,accommodation_type,limit=15)
    hotels = [h for h in (parse_to_hotel(p,accommodation_type) for p in pois) if h]

    cx, cy = centroid  # (lng, lat)
    scored = []
    for h in hotels:
        d = haversine(h.latitude, h.longitude, cy, cx)
        h.distance_note = f"距景点中心 {d:.1f}km"
        scored.append((score_hotel(h.rating, d, transport), h))
    scored.sort(key=lambda x: x[0], reverse=True)
    sorted_hotels = [h for _, h in scored]
    get_session()["hotels"] = sorted_hotels

    top5 = sorted_hotels[:5]
    if not top5:
        return "周边无可用酒店"
    lines = [
        f"- {h.name}（评分 {h.rating}，{h.distance_note}，{h.price_range}）"
        for h in top5
    ]
    return "Top 5 酒店：\n" + "\n".join(lines)


ALL_TOOLS = [search_attractions, get_weather, search_hotels]