# 酒店智能挑选升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `hotel_node` 按景点几何重心做"周边搜索"，并按用户的交通方式给候选酒店打分排序，把最优酒店全程使用。

**Architecture:** graph 拓扑由"三路并行"改为"weather + (attraction→hotel) 并行 → itinerary"。`hotel.py` 重构：新增几何/打分纯函数，把高德 API 从全市 `place/text` 换到周边 `place/around`，`hotel_node` 内部完成排序。`itinerary.py` 不动（`candidate_hotels[0]` 现在天然是最优）。

**Tech Stack:** Python 3.12, LangGraph, Pydantic v2, requests, 高德 v5 POI API

**Spec:** [docs/superpowers/specs/2026-04-21-hotel-smart-selection-design.md](../specs/2026-04-21-hotel-smart-selection-design.md)

---

## File Structure

| 文件 | 改动 | 责任 |
|---|---|---|
| `backend/app/schemas/response.py` | 修改 | `Hotel` 增加 `longitude`/`latitude` |
| `backend/app/agents/hotel.py` | 重构 | 新增几何/打分函数；改用周边搜；hotel_node 内部排序 |
| `backend/app/graph/workflow.py` | 修改 | 拓扑改为 attraction→hotel |
| `backend/app/agents/itinerary.py` | 不动 | 验证 `candidate_hotels[0]` 仍兼容 |

---

## Task 1: Hotel schema 加经纬度字段

**Files:**
- Modify: `backend/app/schemas/response.py:25-32`

- [ ] **Step 1：在 `Hotel` 模型加两个字段**

打开 [backend/app/schemas/response.py](backend/app/schemas/response.py)，把 `Hotel` 类改成：

```python
class Hotel(BaseModel):
    name:str
    address:str
    type:str = Field(...,description="酒店类型，如'经济型酒店'")
    price_range:str = Field(...,description="价格区间，如'300-500'")
    rating:float = Field(default=0,description="评分0-5")
    distance_note:str = Field(default="",description="距景点距离描述，如'距景点中心3.2km'")
    longitude: float = Field(default=0.0, description="经度")
    latitude: float = Field(default=0.0, description="纬度")
```

注：`default=0.0` 是为了兼容 LLM 在 `itinerary_node` 输出 `daily_plans[*].hotel` 时不会编经纬度——后续逻辑会用候选列表里的对象覆盖，所以默认值只是 Pydantic 校验需要。

- [ ] **Step 2：快速冒烟，确认 import 不破**

```bash
cd /Users/admin/AI/travel-agent/backend && python -c "from app.schemas import Hotel; h = Hotel(name='x', address='y', type='经济型酒店', price_range='300-500'); print(h.longitude, h.latitude)"
```
预期输出：`0.0 0.0`

- [ ] **Step 3：提交**

```bash
cd /Users/admin/AI/travel-agent
git add backend/app/schemas/response.py
git commit -m "feat(schema): Hotel 增加 longitude/latitude 字段"
```

---

## Task 2: hotel.py 加纯函数（haversine / compute_centroid / score_hotel）

**Files:**
- Modify: `backend/app/agents/hotel.py`（在文件中插入新函数 + `if __name__ == "__main__":` 自检块）

- [ ] **Step 1：导入 math + Attraction**

在 [backend/app/agents/hotel.py:11-14](backend/app/agents/hotel.py#L11-L14) 顶部 import 区改为：

```python
import os
import math
import requests
from dotenv import load_dotenv
from app.graph.state import TravelState
from app.schemas import Hotel, Attraction
```

- [ ] **Step 2：在 `PRICE_RANGE_MAP` 之后加打分常量**

在 [backend/app/agents/hotel.py:35](backend/app/agents/hotel.py#L35) 之后插入：

```python
# 按交通方式的打分权重 (w_rating, w_distance, max_km)
TRANSPORT_WEIGHTS = {
    "公共交通": (0.6, 0.4, 8.0),
    "自驾":     (0.4, 0.6, 6.0),
    "打车":     (0.4, 0.6, 6.0),
    "步行":     (0.2, 0.8, 3.0),
}
DEFAULT_WEIGHTS = (0.5, 0.5, 8.0)
```

- [ ] **Step 3：加三个纯函数**

紧接着上面的常量，再加：

```python
def compute_centroid(attractions: list[Attraction]) -> tuple[float, float] | None:
    """返回景点几何重心 (lng, lat)。空列表返回 None。"""
    if not attractions:
        return None
    n = len(attractions)
    return (
        sum(a.longitude for a in attractions) / n,
        sum(a.latitude for a in attractions) / n,
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
    w_r, w_d, max_km = TRANSPORT_WEIGHTS.get(transport, DEFAULT_WEIGHTS)
    rating_score = rating / 5
    distance_score = max(0.0, 1 - distance_km / max_km)
    return w_r * rating_score + w_d * distance_score
```

- [ ] **Step 4：在文件末尾加自检 main 块**

参考 [backend/app/agents/attraction.py:82-83](backend/app/agents/attraction.py#L82) 的注释式 main 块写法，在文件末尾加（取消注释，改成可运行的 assert）：

```python
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

    # 3. score_hotel：
    # 公共交通下，rating 4.5 + 距离 2km 应当显著高于 rating 3.0 + 距离 2km
    s_high = score_hotel(4.5, 2.0, "公共交通")
    s_low  = score_hotel(3.0, 2.0, "公共交通")
    assert s_high > s_low, (s_high, s_low)
    # 自驾下，距离权重更大：远酒店扣分更狠
    s_near_drive = score_hotel(4.0, 1.0, "自驾")
    s_far_drive  = score_hotel(4.0, 5.0, "自驾")
    assert s_near_drive > s_far_drive
    # 未知 transport 走 DEFAULT_WEIGHTS，不报错
    score_hotel(4.0, 2.0, "热气球")

    print("[hotel.py self-check] OK")
```

- [ ] **Step 5：跑自检**

```bash
cd /Users/admin/AI/travel-agent/backend && python -m app.agents.hotel
```
预期输出：`[hotel.py self-check] OK`

如果失败，检查是哪条 assert 挂了，修代码（不要修 assert 让它过）。

- [ ] **Step 6：提交**

```bash
cd /Users/admin/AI/travel-agent
git add backend/app/agents/hotel.py
git commit -m "feat(hotel): 加 haversine/compute_centroid/score_hotel 纯函数"
```

---

## Task 3: 切换到周边搜 + 解析经纬度

**Files:**
- Modify: `backend/app/agents/hotel.py`（替换 `fetch_hotels` 和 `parse_to_hotel`）

- [ ] **Step 1：替换 `fetch_hotels`，改名 `fetch_hotels_around`**

把 [backend/app/agents/hotel.py:37-52](backend/app/agents/hotel.py#L37) 的 `fetch_hotels` 整段删掉，改写为：

```python
def fetch_hotels_around(centroid: tuple[float, float], hotel_type: str, limit: int = 15) -> list[dict]:
    """以景点重心为圆心做周边搜，返回高德 POI 原始 dict 列表。"""
    lng, lat = centroid
    url = "https://restapi.amap.com/v5/place/around"
    params = {
        "key": API_KEY,
        "location": f"{lng},{lat}",
        "radius": 10000,                                    # 10km
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
```

- [ ] **Step 2：升级 `parse_to_hotel` 解析经纬度**

把 [backend/app/agents/hotel.py:54-69](backend/app/agents/hotel.py#L54) 的 `parse_to_hotel` 改为：

```python
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
```

注：返回类型从 `Hotel` 变成 `Hotel | None`——下游遍历时要 filter 掉 None。

- [ ] **Step 3：提交（hotel_node 还没改，下个 task 一起跑通）**

```bash
cd /Users/admin/AI/travel-agent
git add backend/app/agents/hotel.py
git commit -m "feat(hotel): place/around 周边搜 + 解析经纬度"
```

---

## Task 4: hotel_node 接入排序 + 兜底

**Files:**
- Modify: `backend/app/agents/hotel.py`（替换 `hotel_node`）

- [ ] **Step 1：重写 `hotel_node`**

把 [backend/app/agents/hotel.py:71-83](backend/app/agents/hotel.py#L71) 的 `hotel_node` 整段替换为：

```python
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
```

- [ ] **Step 2：自检冒烟（不联网，验证 import 仍 OK）**

```bash
cd /Users/admin/AI/travel-agent/backend && python -m app.agents.hotel
```
预期输出仍是 `[hotel.py self-check] OK`（self-check 块只测纯函数，不会调高德）。

- [ ] **Step 3：提交**

```bash
cd /Users/admin/AI/travel-agent
git add backend/app/agents/hotel.py
git commit -m "feat(hotel): hotel_node 按交通方式打分排序，输出真实距离"
```

---

## Task 5: graph 拓扑改 attraction → hotel

**Files:**
- Modify: `backend/app/graph/workflow.py:17-20`

- [ ] **Step 1：改边**

打开 [backend/app/graph/workflow.py](backend/app/graph/workflow.py)，把 L17-20 三条 START 边改为两条：

旧：
```python
# 扇出：START 同时发往三个数据源（并行执行）
builder.add_edge(START, "weather")
builder.add_edge(START, "attraction")
builder.add_edge(START, "hotel")
```

新：
```python
# 扇出：weather 与 attraction 并行；hotel 依赖 attraction（要算景点重心）
builder.add_edge(START, "weather")
builder.add_edge(START, "attraction")
builder.add_edge("attraction", "hotel")
```

L22-24 三条入 itinerary 的边**保持不变**——itinerary 仍然 join 三路结果。

- [ ] **Step 2：可视化（可选但推荐——LangGraph 学习点）**

```bash
cd /Users/admin/AI/travel-agent/backend && python -c "from app.graph.workflow import graph; graph.get_graph().draw_mermaid_png(output_file_path='workflow.png')"
```
打开 [backend/workflow.png](backend/workflow.png) 看新拓扑：weather 从 START 出，attraction 从 START 出 → hotel，三个汇合到 itinerary。

- [ ] **Step 3：提交**

```bash
cd /Users/admin/AI/travel-agent
git add backend/app/graph/workflow.py backend/workflow.png
git commit -m "feat(graph): hotel 改为依赖 attraction，attraction→hotel"
```

---

## Task 6: 端到端手工验证

**Files:** 仅运行，无修改

- [ ] **Step 1：起后端**

```bash
cd /Users/admin/AI/travel-agent/backend && uvicorn app.main:app --reload --port 8000
```
后台运行，确认日志没报错。

- [ ] **Step 2：发一次"公共交通"请求**

新开终端：

```bash
curl -X POST http://localhost:8000/plan \
  -H "Content-Type: application/json" \
  -d '{"destination":"北京","start_date":"2026-05-01","end_date":"2026-05-03","transport":"公共交通","accommodation":"舒适型酒店","preferences":["历史文化"]}'
```

注：`/plan` 是猜测的接口名，按你 `main.py` 实际路径替换。

**核对后端日志**：
- `[AttractionAgent] 找到 N 个景点`
- `[HotelAgent] 查询 北京 的 舒适型酒店（候选景点 N 个）`
- `[HotelAgent] 共 M 家，最优：XX（距景点中心 X.Xkm, 评分 X.X）`

**核对返回 JSON**：`daily_plans[*].hotel.distance_note` 应该是真实公里数（如 `距景点中心 3.2km`），不是旧的"距离景点5公里"。

- [ ] **Step 3：换"自驾"再发一次，看排序是否变化**

```bash
curl -X POST http://localhost:8000/plan \
  -H "Content-Type: application/json" \
  -d '{"destination":"北京","start_date":"2026-05-01","end_date":"2026-05-03","transport":"自驾","accommodation":"舒适型酒店","preferences":["历史文化"]}'
```

预期：日志里"最优"那家可能换了一家——自驾下距离权重 0.6 > 公共交通的 0.4，距离近的酒店更容易胜出。

- [ ] **Step 4：fallback 路径手工模拟（可选）**

把 `attraction.py` 的 `POI_TYPES` 临时改成乱码（如 `"999999"`）让它返回空，再发一次请求，确认日志显示 `[HotelAgent] 无景点重心，退回按城市搜`，且返回里仍有酒店。

验证完**记得改回 `POI_TYPES = "110000|140100"`**。

- [ ] **Step 5：前端目检**

打开前端，下单后看 HotelCard / DailyPlan 的 `distance_note` 是真实公里数。

- [ ] **Step 6：提交（如果上面有任何小修复）**

```bash
cd /Users/admin/AI/travel-agent
git status   # 看有没有要提交的
```
若有改动：
```bash
git add -p   # 挑选性 stage
git commit -m "fix(hotel): 端到端验证发现的小修"
```
若无改动则跳过此步。

---

## Self-Review

**Spec 覆盖检查（对照 [spec §做](../specs/2026-04-21-hotel-smart-selection-design.md)）：**
- ✅ 拓扑 attraction→hotel — Task 5
- ✅ Hotel schema 加经纬度 — Task 1
- ✅ compute_centroid / haversine / score_hotel — Task 2
- ✅ place/around 周边搜 — Task 3
- ✅ parse_to_hotel 解析经纬度 — Task 3
- ✅ distance_note 写真实距离 — Task 4
- ✅ itinerary.py 不动 — File Structure 表已声明，Task 6 间接验证
- ✅ §7 边界（景点空 / API 0 家 / location 缺失 / rating 空 / 未知 transport）— 分散在 Task 3 (parse 返 None)、Task 4 (centroid None fallback、外层 try/except)、Task 2 (DEFAULT_WEIGHTS)

**Placeholder 扫描：** 无 TBD/TODO/"appropriate"。所有代码块都是完整代码。

**类型/命名一致性：**
- `compute_centroid` 返回 `tuple[float, float] | None`，Task 4 用 `if centroid is None:` ✓
- `parse_to_hotel` 返回 `Hotel | None`，Task 4 用 `[h for h in (...) if h]` 过滤 ✓
- `fetch_hotels_around` / `fetch_hotels_by_city` 名字在 Task 3 定义，Task 4 调用一致 ✓
- `TRANSPORT_WEIGHTS` 在 Task 2 定义，Task 2 的 `score_hotel` 引用 ✓
