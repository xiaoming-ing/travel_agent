import difflib
import logging

from app.planning.validator import remove_cross_day_duplicates
from app.providers.attractions import parse_to_attraction, search_attraction_by_name
from app.schemas import Attraction, Hotel, TripPlan

logger = logging.getLogger(__name__)


def _resolve_coords(
    attraction: Attraction,
    raw_attractions: list[Attraction],
    city: str,
) -> None:
    """按同名、模糊匹配、POI 查询的顺序补全景点信息。"""
    by_name = {item.name: item for item in raw_attractions}
    hit = by_name.get(attraction.name)
    if hit:
        _copy_location(attraction, hit)
        return

    matches = difflib.get_close_matches(
        attraction.name, list(by_name.keys()), n=1, cutoff=0.8
    )
    if matches:
        hit = by_name[matches[0]]
        logger.debug("[resolve_coords] 模糊匹配：'%s' → '%s'", attraction.name, hit.name)
        _copy_location(attraction, hit)
        return

    poi = search_attraction_by_name(city, attraction.name)
    resolved = parse_to_attraction(poi) if poi else None
    if resolved:
        logger.debug(
            "[resolve_coords] POI 补全：'%s' → (%s, %s)",
            attraction.name,
            resolved.longitude,
            resolved.latitude,
        )
        _copy_location(attraction, resolved)
        return
    logger.warning("[resolve_coords] 无法解析坐标：'%s'，前端会把它从地图过滤掉", attraction.name)


def _copy_location(target: Attraction, source: Attraction) -> None:
    target.longitude = source.longitude
    target.latitude = source.latitude
    target.address = source.address
    if not target.image_url:
        target.image_url = source.image_url


def _postprocess_plan(
    result: TripPlan,
    raw_attractions: list[Attraction],
    hotels: list[Hotel],
    weather: list[dict],
    destination: str,
) -> dict:
    for attraction in result.attractions:
        _resolve_coords(attraction, raw_attractions, destination)
    result.hotels = hotels[:3]
    if not weather:
        result.weather_summary = "⚠️ 天气数据暂未获取，建议出行前通过天气 App 查询"
    return remove_cross_day_duplicates(result.model_dump(mode="json"))
