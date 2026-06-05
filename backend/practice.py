from app.schemas import Attraction
def computed_centroid(loacations):
    """计算几何中心"""
    if not loacations:
        return None
    n = len(loacations)
    return (
        sum(loc.longitude for loc in loacations) / n,
        sum(loc.latitude for loc in loacations) / n,
    )

a1 = Attraction(name="x", address="", longitude=116.0, latitude=39.0,
                duration_minutes=0, ticket_price=0, description="")
a2 = Attraction(name="y", address="", longitude=116.4, latitude=39.4,
                duration_minutes=0, ticket_price=0, description="")


TRANSPORT_WEIGHTS = {
    "公共交通": (0.6, 0.4, 8.0),
    "自驾":     (0.4, 0.6, 6.0),
    "打车":     (0.4, 0.6, 6.0),
    "步行":     (0.2, 0.8, 1.0),
}
DEFAULT_WEIGHTS = (0.5, 0.5, 8.0)

def my_score_hotel(rating: float, distance_km:float, transport: str) -> float:
    weights = TRANSPORT_WEIGHTS.get(transport, DEFAULT_WEIGHTS)
    w_rating, w_distance, max_km = weights
    print(w_rating, w_distance, max_km, distance_km)
    rating_score = rating / 5.0
    distance_score = max(0, 1 - distance_km / max_km)
    return w_rating * rating_score + w_distance * distance_score

print(my_score_hotel(4.5, 1.0, "步行"))   # 应该比下面这个高
print(my_score_hotel(4.5, 2.5, "步行")) 