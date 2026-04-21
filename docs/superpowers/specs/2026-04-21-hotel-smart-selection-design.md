# 酒店智能挑选升级（按交通方式打分）

## 背景

当前 `hotel.py` 的逻辑：
- 按用户的住宿偏好（经济型/舒适型/豪华型/民宿）调用高德 `place/text` 在全市范围搜 5 家
- `parse_to_hotel` 没有保存经纬度，`distance_note` 是硬编码的字符串 `"距离景点5公里"`
- `itinerary.py` L114-117 直接 `default_hotel = candidate_hotels[0]`，把列表里第一家应用到所有 daily_plans

问题：
1. 候选酒店的地理位置完全随机（高德全市搜返回什么算什么）
2. 没有任何"哪家更合适"的判断逻辑
3. `distance_note` 是假数据，前端展示不可信
4. 用户的"交通方式"字段没有被酒店选择利用

用户的真实需求是：**全程订一家酒店**（节假日临时换酒店容易涨价），并且这家酒店的选择要结合交通方式：
- 公共交通：舒适度高 + 离所有景区都不太远
- 自驾/打车：离景点近 + 舒适度
- 步行：必须很近

## 目标

让 `hotel_node` 能根据**景点分布的几何中心**和**用户的交通方式**，从一组合理候选里打分挑出最优的全程酒店，并把真实距离写进 `distance_note`。

## 范围

**做：**
1. graph 拓扑：`attraction → hotel`（hotel 不再从 START 并行，而是依赖 attraction 完成）
2. `Hotel` schema 增加 `longitude` / `latitude` 字段
3. `hotel.py` 重构：
   - 新增 `compute_centroid(attractions)`：算景点经纬度的几何中心
   - 把 `fetch_hotels` 从 `place/text` 全市搜改为 `place/around` 周边搜（中心点 = 景点重心，半径 = 10km）
   - `parse_to_hotel` 解析 `location` 字段，存经纬度
   - 新增 `haversine(lat1, lng1, lat2, lng2)`：算两点公里距离
   - 新增 `score_hotel(hotel, centroid, transport)`：按交通方式权重打分
   - `hotel_node` 把候选按 score 降序排，并把真实距离写进每家的 `distance_note`
4. `itinerary.py` 第 114-117 行不动（`candidate_hotels[0]` 现在天然就是最优）

**不做（留给下一个 spec）：**
- 每天景点的地理顺序排序
- "近地铁" 维度（YAGNI；以后可作为 `score_hotel` 的扩展）
- 多酒店分段方案

## 设计

### 1. graph 拓扑

```
START ─┬─→ weather ──┐
       │             │
       └─→ attraction ─→ hotel ──→ itinerary ─→ END
```

`attraction` 和 `weather` 仍然并行；`hotel` 改为依赖 `attraction`。`itinerary` 等三个上游都完成。

### 2. Hotel schema 改动

[backend/app/schemas/response.py](backend/app/schemas/response.py) 的 `Hotel` 增加：

```python
longitude: float = Field(default=0.0, description="经度")
latitude: float = Field(default=0.0, description="纬度")
```

默认 0.0 是为了兼容 LLM 输出（itinerary 里 LLM 不会编经纬度，但 Pydantic 校验需要默认值兜底）。

### 3. 打分公式

模块级常量，一个表 + 一个函数：

```python
# (w_rating, w_distance, max_km)
TRANSPORT_WEIGHTS = {
    "公共交通": (0.6, 0.4, 8),
    "自驾":     (0.4, 0.6, 6),
    "打车":     (0.4, 0.6, 6),
    "步行":     (0.2, 0.8, 3),
}
DEFAULT_WEIGHTS = (0.5, 0.5, 8)  # 兜底（未知交通方式）

def score_hotel(rating: float, distance_km: float, transport: str) -> float:
    w_r, w_d, max_km = TRANSPORT_WEIGHTS.get(transport, DEFAULT_WEIGHTS)
    rating_score = rating / 5
    distance_score = max(0, 1 - distance_km / max_km)
    return w_r * rating_score + w_d * distance_score
```

### 4. 几何中心 + haversine

```python
import math

def compute_centroid(attractions: list[Attraction]) -> tuple[float, float] | None:
    """返回 (lng, lat)。空列表返回 None。"""
    if not attractions:
        return None
    n = len(attractions)
    return (
        sum(a.longitude for a in attractions) / n,
        sum(a.latitude for a in attractions) / n,
    )

def haversine(lat1, lng1, lat2, lng2) -> float:
    """两点经纬度之间的公里距离。"""
    R = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dlng/2)**2
    return 2 * R * math.asin(math.sqrt(a))
```

注：算术平均的"重心"对景点分布均匀的城市够用；少数景点偏远也只会把酒店稍微拉过去一点，不会失控。复杂的"加权中心"YAGNI。

### 5. 高德周边搜索

API 改为 [`place/around`](https://restapi.amap.com/v5/place/around)（v5）：

```python
params = {
    "key": API_KEY,
    "location": f"{centroid_lng},{centroid_lat}",
    "radius": 10000,                                   # 10km
    "types": ACCOMMODATION_TYPE_MAP[hotel_type],
    "page_size": 15,                                   # 多搜一些供打分
    "show_fields": "business",
    "sortrule": "weight",                              # 按高德综合权重初排
}
```

`page_size` 从 5 提到 15，给打分阶段一个像样的候选池。

### 6. hotel_node 主流程

```python
def hotel_node(state: TravelState) -> dict:
    req = state["request"]
    attractions = state.get("attractions_raw", [])

    centroid = compute_centroid(attractions)
    if centroid is None:
        # 景点都没拿到，退回旧逻辑：按城市搜，不打分
        return {"hotels_raw": _fallback_fetch_by_city(req)}

    pois = fetch_hotels_around(centroid, req.accommodation, limit=15)
    hotels = [parse_to_hotel(p, req.accommodation) for p in pois]

    # 算距离 + 打分 + 排序 + 写 distance_note
    centroid_lng, centroid_lat = centroid
    scored = []
    for h in hotels:
        d = haversine(h.latitude, h.longitude, centroid_lat, centroid_lng)
        h.distance_note = f"距景点中心 {d:.1f}km"
        s = score_hotel(h.rating, d, req.transport)
        scored.append((s, h))

    scored.sort(key=lambda x: x[0], reverse=True)
    return {"hotels_raw": [h for _, h in scored]}
```

### 7. 边界与异常

| 情况 | 行为 |
|---|---|
| `attractions_raw` 为空 | 退回按城市搜的旧逻辑（保证 itinerary 节点仍能拿到酒店） |
| 高德返回 0 家 | `hotels_raw = []`，itinerary 走 `if candidate_hotels:` 兜底分支 |
| 酒店 POI 没有 `location` | 该家舍弃（无法计算距离） |
| `rating` 为空字符串 | 现有 `parse_to_hotel` 已经兜到 0.0，自然得低分 |
| `transport` 不在表里 | 用 `DEFAULT_WEIGHTS` 兜底 |

### 8. 不变的部分

- 调用方（`itinerary_node`）不需要任何改动——`candidate_hotels[0]` 现在天然就是打分最高的那家
- 前端不需要改——`Hotel` 新增的经纬度字段是可选的，旧字段含义不变
- 其他 agent（weather, attraction）完全不动

## 验证方式

1. 跑一次完整 workflow（北京 3 天，公共交通），打 log 看候选酒店的 score 排序、`distance_note` 是不是真实距离
2. 同样输入换成 `transport="自驾"`，看排序是否变化（理论上偏远但豪华的酒店在公共交通下排前面，在自驾下也靠前但优势缩小）
3. 故意让 attraction_node 返回空（mock），确认 fallback 走通
4. 前端 `HotelCard` 渲染 `distance_note` 应该看到真实公里数
