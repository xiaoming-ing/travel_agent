"""行程修订使用的确定性工具。"""

from langchain_core.tools import tool

from app.providers.attractions import parse_to_attraction, search_attraction_by_name
from app.providers.hotels import (
    compute_centroid,
    fetch_hotels_around,
    haversine,
    parse_to_hotel,
    score_hotel,
)
from app.revision.context import get_ctx
from app.schemas import Attraction, TravelIntent


def _validate_day(plan: dict, day: int) -> str | None:
    if day < 1 or day > len(plan.get("daily_plans", [])):
        return f"day={day} 超出范围（行程共 {len(plan.get('daily_plans', []))} 天）"
    return None


def _resolve_attraction(name: str) -> Attraction | None:
    context = get_ctx()
    for attraction in context.get("raw_attractions", []):
        if attraction.name == name:
            return attraction
    city = context.get("plan", {}).get("destination", "")
    poi = search_attraction_by_name(city, name)
    attraction = parse_to_attraction(poi) if poi else None
    if attraction is not None:
        context.setdefault("raw_attractions", []).append(attraction)
    return attraction


@tool
def add_attraction(day: int, attraction_name: str) -> str:
    """向指定一天增加一个具体景点，不能造成跨天重复。"""
    plan = get_ctx()["plan"]
    error = _validate_day(plan, day)
    if error:
        return error
    used_names = {
        name
        for daily in plan["daily_plans"]
        for name in daily.get("attraction_names", [])
    }
    if attraction_name in used_names:
        return f"景点 {attraction_name!r} 已经在行程中"
    attraction = _resolve_attraction(attraction_name)
    if attraction is None:
        return f"景点 {attraction_name!r} 未找到"
    plan_names = {item["name"] for item in plan.get("attractions", [])}
    if attraction.name not in plan_names:
        plan.setdefault("attractions", []).append(attraction.model_dump(mode="json"))
    plan["daily_plans"][day - 1].setdefault("attraction_names", []).append(
        attraction.name
    )
    return f"已向 Day {day} 增加景点：{attraction.name}"


@tool
def remove_attraction(day: int, attraction_name: str) -> str:
    """从指定一天移除一个景点。"""
    plan = get_ctx()["plan"]
    error = _validate_day(plan, day)
    if error:
        return error
    names = plan["daily_plans"][day - 1].get("attraction_names", [])
    if attraction_name not in names:
        return f"Day {day} 中没有景点 {attraction_name!r}"
    plan["daily_plans"][day - 1]["attraction_names"] = [
        name for name in names if name != attraction_name
    ]
    return f"已从 Day {day} 移除景点：{attraction_name}"


@tool
def change_day_pace(day: int, max_attractions: int) -> str:
    """通过限制当天景点数量调整节奏，max_attractions 只能是 1 或 2。"""
    plan = get_ctx()["plan"]
    error = _validate_day(plan, day)
    if error:
        return error
    if max_attractions not in {1, 2}:
        return "max_attractions 只能是 1 或 2"
    names = plan["daily_plans"][day - 1].get("attraction_names", [])
    plan["daily_plans"][day - 1]["attraction_names"] = names[:max_attractions]
    return f"Day {day} 已调整为最多 {max_attractions} 个景点"


@tool
def change_transport(new_transport: str, day: int | None = None) -> str:
    """修改全部行程或指定一天的交通方式。"""
    valid = {"公共交通", "自驾", "打车", "步行"}
    if new_transport not in valid:
        return f"new_transport 必须是{valid}之一"
    plan = get_ctx()["plan"]
    if day is None:
        for daily in plan.get("daily_plans", []):
            daily["transport"] = new_transport
        get_ctx()["transport"] = new_transport
        return f"全部行程交通方式已改为：{new_transport}"
    error = _validate_day(plan, day)
    if error:
        return error
    plan["daily_plans"][day - 1]["transport"] = new_transport
    return f"Day {day} 交通方式已改为：{new_transport}"


@tool
def update_meal_constraints(restrictions: list[str]) -> str:
    """把饮食限制同步到每天的餐饮建议中。"""
    cleaned = list(dict.fromkeys(item.strip() for item in restrictions if item.strip()))
    if not cleaned:
        return "restrictions 不能为空"
    warning = f"请避开{'、'.join(cleaned)}，实际配料及交叉污染需向餐厅确认"
    for daily in get_ctx()["plan"].get("daily_plans", []):
        meals = daily.get("meals", {})
        for meal in ("breakfast", "lunch", "dinner"):
            current = str(meals.get(meal, "")).strip()
            if warning not in current:
                meals[meal] = f"{current}（{warning}）" if current else warning
    intent = get_ctx().get("intent", TravelIntent())
    data = intent.model_dump()
    data["dietary_restrictions"] = list(
        dict.fromkeys([*data["dietary_restrictions"], *cleaned])
    )
    get_ctx()["intent"] = TravelIntent.model_validate(data)
    return f"已更新饮食限制：{'、'.join(cleaned)}"


@tool
def update_budget_limit(new_limit: int) -> str:
    """更新整个行程的总预算上限，并报告当前预算是否超限。"""
    if new_limit <= 0:
        return "new_limit 必须大于 0"
    intent = get_ctx().get("intent", TravelIntent())
    get_ctx()["intent"] = intent.model_copy(update={"budget_limit": new_limit})
    budget = get_ctx()["plan"].get("budget", {})
    total = sum(
        float(budget.get(key, 0) or 0)
        for key in ("attractions", "hotel", "meals", "transport")
    )
    if total > new_limit:
        return f"预算上限已更新为 {new_limit} 元，但当前估算 {total:g} 元仍然超限"
    return f"预算上限已更新为 {new_limit} 元，当前估算未超限"


@tool
def replace_day_attractions(day: int, new_attraction_names: list[str]) -> str:
    """把指定一天的景点整组替换为新名字列表。"""
    plan = get_ctx()["plan"]
    city = plan.get("destination", "")
    error = _validate_day(plan, day)
    if error:
        return error

    all_names = {attraction.name for attraction in get_ctx()["raw_attractions"]}
    auto_added: list[str] = []
    resolved_names: list[str] = []
    for name in new_attraction_names:
        if name in all_names:
            resolved_names.append(name)
            if name not in {item["name"] for item in plan["attractions"]}:
                attraction = next(
                    (
                        item
                        for item in get_ctx()["raw_attractions"]
                        if item.name == name
                    ),
                    None,
                )
                if attraction:
                    plan["attractions"].append(attraction.model_dump(mode="json"))
            continue

        poi = search_attraction_by_name(city, name)
        if not poi:
            return f"景点 {name!r} 在高德 POI 里没找到。名字可能不准确，请换个说法。"
        new_attraction = parse_to_attraction(poi)
        if not new_attraction:
            return f"景点 {name!r} 数据解析失败"
        real_name = new_attraction.name
        get_ctx()["raw_attractions"].append(new_attraction)
        all_names.add(real_name)
        existing = {item["name"] for item in plan["attractions"]}
        if real_name not in existing:
            plan["attractions"].append(new_attraction.model_dump(mode="json"))
        auto_added.append(real_name)
        resolved_names.append(real_name)

    used_in_other_days: set[str] = set()
    for index, daily in enumerate(plan["daily_plans"]):
        if index != day - 1:
            used_in_other_days.update(daily["attraction_names"])
    duplicates = [name for name in resolved_names if name in used_in_other_days]
    if duplicates:
        return (
            f"这些景点已在其他天安排：{duplicates}，会重复。"
            "请换别的，或先明确要不要从其他天移除。"
        )

    plan["daily_plans"][day - 1]["attraction_names"] = resolved_names
    message = f"Day {day} 景点已更新为：{', '.join(resolved_names)}"
    if auto_added:
        message += f"（新加到候选库：{', '.join(auto_added)}）"
    return message


@tool
def change_hotel_type(new_type: str) -> str:
    """按新档次重新搜索酒店，并按交通方式综合打分。"""
    valid = {"经济型酒店", "舒适型酒店", "豪华型酒店", "民宿"}
    if new_type not in valid:
        return f"new_type 必须是{valid}之一"
    raw_attractions = get_ctx()["raw_attractions"]
    if not raw_attractions:
        return "无候选景点，无法计算酒店中心"
    centroid = compute_centroid(raw_attractions)
    if centroid is None:
        return "景点坐标无效"
    pois = fetch_hotels_around(centroid, new_type, limit=15)
    hotels = [
        hotel
        for hotel in (parse_to_hotel(poi, new_type) for poi in pois)
        if hotel
    ]
    cx, cy = centroid
    scored = []
    transport = get_ctx().get("transport", "公共交通")
    for hotel in hotels:
        distance = haversine(hotel.latitude, hotel.longitude, cy, cx)
        hotel.distance_note = f"距景点中心 {distance:.1f}km"
        scored.append((score_hotel(hotel.rating, distance, transport), hotel))
    scored.sort(key=lambda item: item[0], reverse=True)
    top_three = [hotel for _, hotel in scored[:3]]
    get_ctx()["plan"]["hotels"] = [
        hotel.model_dump(mode="json") for hotel in top_three
    ]
    return f"酒店已改为 {new_type}，Top3：{', '.join(hotel.name for hotel in top_three)}"


REVISE_TOOLS = [
    add_attraction,
    remove_attraction,
    replace_day_attractions,
    change_hotel_type,
    change_day_pace,
    change_transport,
    update_meal_constraints,
    update_budget_limit,
]
