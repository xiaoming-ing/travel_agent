# 长期记忆(偏好画像)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让旅行助手跨对话记住用户的 3 个结构化偏好(口味/住宿/交通),下次新开行程时表单自动预选。

**Architecture:** 自建一张 SQLite `user_preferences` 表 + async 工具函数(不使用 LangGraph 官方 Store、不升级依赖)。读发生在前端(表单挂载时拉画像当默认值),写发生在后端(行程完成时把最终 request 的 3 字段 UPSERT 回表)。user_id 由前端生成存 localStorage 随请求带上。

**Tech Stack:** Python 3.13 / FastAPI / aiosqlite / pytest(asyncio_mode=auto);Vue 3 + TypeScript + Vite。

## Global Constraints

- 不升级 `langgraph` / `langgraph-checkpoint-sqlite` 等依赖。
- 不使用 LangGraph 官方 Store(`compile(store=...)`)。
- 只记 3 个字段:`preferences`(JSON 数组)、`accommodation`、`transport`;**不**记 `extra_requirements`。
- 存储位置:现有 `checkpoints.db`,表名 `user_preferences`;DB 路径取环境变量 `CHECKPOINTS_DB`(默认 `checkpoints.db`)。
- user_id 来源:前端 `localStorage['travel_user_id']`,缺失则 `crypto.randomUUID()` 生成。
- 写入时机:**仅行程完成时写一次**。
- 偏好写入失败**不得**中断主流程(记日志并吞掉异常)。
- 后端测试从 `backend/` 目录运行 `pytest`。

## File Structure

- Create `backend/app/graph/preferences_store.py` — 表 + 读/写/归一化函数(本特性的数据层,单一职责)
- Create `backend/tests/test_preferences_store.py` — 数据层单测
- Create `backend/tests/test_preferences_api.py` — GET 接口单测
- Modify `backend/app/graph/conversation_store.py` — `conversations` 表加 `user_id` 列 + 创建时写入
- Modify `backend/app/main.py` — lifespan 建表、GET 接口、`ChatStartBody.user_id`、完成时写画像
- Create `frontend/src/userId.ts` — user_id 工具
- Modify `frontend/src/api.ts` — `getPreferences` + start 请求带 user_id
- Modify `frontend/src/views/FormView.vue` — 挂载时预选表单

---

### Task 1: 偏好数据层 `preferences_store.py`

**Files:**
- Create: `backend/app/graph/preferences_store.py`
- Test: `backend/tests/test_preferences_store.py`

**Interfaces:**
- Produces:
  - `async init_pref_table() -> None`
  - `async get_preferences(user_id: str) -> dict | None`(命中返回 `{"preferences": list[str], "accommodation": str, "transport": str}`,未命中 `None`)
  - `async save_preferences(user_id: str, preferences: list[str], accommodation: str, transport: str) -> None`(UPSERT)
  - `pref_fields_from_request(request) -> dict`(同步;兼容 `TripRequest` 对象与 dict,返回上面 3 键)
  - `async save_preferences_from_request(user_id: str, request) -> None`
  - 模块级 `DB_PATH`(取 `os.getenv("CHECKPOINTS_DB", "checkpoints.db")`)

- [ ] **Step 1: 写失败测试**

`backend/tests/test_preferences_store.py`:

```python
import json
import aiosqlite
import pytest
from datetime import date
from app.graph import preferences_store as ps


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db = str(tmp_path / "test_prefs.db")
    monkeypatch.setattr(ps, "DB_PATH", db)
    return db


async def test_save_then_get_roundtrip(tmp_db):
    await ps.init_pref_table()
    await ps.save_preferences("u1", ["历史文化", "美食"], "豪华型酒店", "自驾")
    got = await ps.get_preferences("u1")
    assert got == {
        "preferences": ["历史文化", "美食"],
        "accommodation": "豪华型酒店",
        "transport": "自驾",
    }


async def test_get_miss_returns_none(tmp_db):
    await ps.init_pref_table()
    assert await ps.get_preferences("nobody") is None


async def test_save_is_upsert_no_duplicate(tmp_db):
    await ps.init_pref_table()
    await ps.save_preferences("u1", ["美食"], "经济型酒店", "公共交通")
    await ps.save_preferences("u1", ["艺术"], "民宿", "步行")
    got = await ps.get_preferences("u1")
    assert got["preferences"] == ["艺术"]
    assert got["accommodation"] == "民宿"
    async with aiosqlite.connect(tmp_db) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM user_preferences WHERE user_id='u1'"
        ) as cur:
            (count,) = await cur.fetchone()
    assert count == 1


def test_pref_fields_from_request_handles_dict():
    f = ps.pref_fields_from_request(
        {"preferences": ["美食"], "accommodation": "民宿", "transport": "步行"}
    )
    assert f == {"preferences": ["美食"], "accommodation": "民宿", "transport": "步行"}


def test_pref_fields_from_request_handles_object():
    from app.schemas import TripRequest
    req = TripRequest(
        destination="南京",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 3),
        preferences=["历史文化"],
        accommodation="豪华型酒店",
        transport="自驾",
    )
    f = ps.pref_fields_from_request(req)
    assert f == {
        "preferences": ["历史文化"],
        "accommodation": "豪华型酒店",
        "transport": "自驾",
    }
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_preferences_store.py -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'app.graph.preferences_store'`)

- [ ] **Step 3: 写实现**

`backend/app/graph/preferences_store.py`:

```python
"""
user_preferences 表: 跨对话的长期记忆，按 user_id 存旅行偏好(口味/住宿/交通)。
和 conversations / LangGraph checkpoints 共用同一个 SQLite 文件。
"""
import os
import json
import aiosqlite
from datetime import datetime

DB_PATH = os.getenv("CHECKPOINTS_DB", "checkpoints.db")


async def init_pref_table() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                preferences TEXT,
                accommodation TEXT,
                transport TEXT,
                updated_at TEXT
            )
            """
        )
        await db.commit()


async def get_preferences(user_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT preferences, accommodation, transport "
            "FROM user_preferences WHERE user_id=?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    try:
        prefs = json.loads(row["preferences"]) if row["preferences"] else []
    except (json.JSONDecodeError, TypeError):
        prefs = []
    return {
        "preferences": prefs,
        "accommodation": row["accommodation"] or "",
        "transport": row["transport"] or "",
    }


async def save_preferences(
    user_id: str, preferences: list[str], accommodation: str, transport: str
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO user_preferences
                (user_id, preferences, accommodation, transport, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                preferences=excluded.preferences,
                accommodation=excluded.accommodation,
                transport=excluded.transport,
                updated_at=excluded.updated_at
            """,
            (
                user_id,
                json.dumps(preferences, ensure_ascii=False),
                accommodation,
                transport,
                datetime.now().isoformat(),
            ),
        )
        await db.commit()


def pref_fields_from_request(request) -> dict:
    """从 TripRequest 对象或其 dict 形态(checkpointer 回读后可能是 dict)取出 3 个字段。"""
    if isinstance(request, dict):
        prefs = request.get("preferences") or []
        acc = request.get("accommodation") or ""
        trans = request.get("transport") or ""
    else:
        prefs = getattr(request, "preferences", None) or []
        acc = getattr(request, "accommodation", None) or ""
        trans = getattr(request, "transport", None) or ""
    return {"preferences": list(prefs), "accommodation": acc, "transport": trans}


async def save_preferences_from_request(user_id: str, request) -> None:
    f = pref_fields_from_request(request)
    await save_preferences(
        user_id, f["preferences"], f["accommodation"], f["transport"]
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_preferences_store.py -v`
Expected: PASS(5 passed)

- [ ] **Step 5: 提交**

```bash
git add backend/app/graph/preferences_store.py backend/tests/test_preferences_store.py
git commit -m "feat: 偏好长期记忆数据层(user_preferences 表 + 读写)"
```

---

### Task 2: `conversations` 表增加 `user_id` 列

**Files:**
- Modify: `backend/app/graph/conversation_store.py`
- Test: `backend/tests/test_conversation_store.py`(新建)

**Interfaces:**
- Consumes: 无
- Produces:
  - `create_conversation(thread_id, destination, start_date, end_date, user_id: str = "")`(新增末位参数)
  - `get_conversation(thread_id)` 返回的 dict 现包含 `"user_id"` 键(因 `SELECT *`)

**注意:** 现有 `checkpoints.db` 已存在不含 `user_id` 列的 `conversations` 表,`CREATE TABLE IF NOT EXISTS` 不会补列。需在 `init_table` 里做幂等迁移(`ALTER TABLE ... ADD COLUMN`,已存在则忽略)。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_conversation_store.py`:

```python
import pytest
from app.graph import conversation_store as cs


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db = str(tmp_path / "test_conv.db")
    monkeypatch.setattr(cs, "DB_PATH", db)
    return db


async def test_create_conversation_stores_user_id(tmp_db):
    await cs.init_table()
    await cs.create_conversation(
        "t1", "南京", "2026-07-01", "2026-07-03", user_id="u1"
    )
    conv = await cs.get_conversation("t1")
    assert conv["user_id"] == "u1"


async def test_create_conversation_user_id_defaults_empty(tmp_db):
    await cs.init_table()
    await cs.create_conversation("t2", "成都", "2026-07-01", "2026-07-03")
    conv = await cs.get_conversation("t2")
    assert conv["user_id"] == ""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_conversation_store.py -v`
Expected: FAIL(`create_conversation()` 不接受 `user_id` 参数 / 返回 dict 无 `user_id` 键)

- [ ] **Step 3: 写实现**

在 `backend/app/graph/conversation_store.py` 中:

(a) `init_table` 的建表语句加列,并补幂等迁移。把现有 `init_table` 整个替换为:

```python
async def init_table() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                thread_id TEXT PRIMARY KEY,
                title TEXT,
                destination TEXT,
                create_at TEXT,
                status TEXT DEFAULT 'active',
                trip_plan TEXT,
                user_id TEXT DEFAULT ''
            )
            """)
        # 幂等迁移：老库已有 conversations 表但缺 user_id 列时补上
        try:
            await db.execute("ALTER TABLE conversations ADD COLUMN user_id TEXT DEFAULT ''")
        except Exception:
            pass  # 列已存在
        await db.commit()
```

(b) `create_conversation` 加参数与列。整体替换为:

```python
async def create_conversation(
    thread_id: str, destination: str, start_date: str, end_date: str, user_id: str = ""
) -> None:
    title = f"{destination}{start_date} ~ {end_date}"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO conversations"
            "(thread_id,title,destination,create_at,user_id) VALUES (?,?,?,?,?)",
            (thread_id, title, destination, datetime.now().isoformat(), user_id)
        )
        await db.commit()
```

- [ ] **Step 4: 跑测试确认通过 + 回归**

Run: `cd backend && python -m pytest tests/test_conversation_store.py tests/test_conversation.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/graph/conversation_store.py backend/tests/test_conversation_store.py
git commit -m "feat: conversations 表增加 user_id 列"
```

---

### Task 3: 后端接线(建表 + GET 接口 + 完成时写画像)

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_preferences_api.py`(新建)

**Interfaces:**
- Consumes: Task 1 的 `init_pref_table` / `get_preferences` / `save_preferences_from_request`;Task 2 的 `create_conversation(..., user_id=)` 与 `get_conversation` 含 `user_id`
- Produces:
  - `GET /api/preferences/{user_id}` → 命中返回 3 字段 dict,未命中返回 `{}`
  - `ChatStartBody` 新增 `user_id: str = ""`
  - 模块级 `async _persist_preferences(graph, config, thread_id) -> None`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_preferences_api.py`:

```python
import asyncio
from fastapi.testclient import TestClient
from app.graph import preferences_store as ps


def test_get_preferences_hit_and_miss(tmp_path, monkeypatch):
    db = str(tmp_path / "api.db")
    monkeypatch.setattr(ps, "DB_PATH", db)
    asyncio.run(ps.init_pref_table())
    asyncio.run(ps.save_preferences("u1", ["美食"], "民宿", "步行"))

    from app.main import app
    client = TestClient(app)  # 不用 with：GET 接口不依赖 lifespan/图

    r = client.get("/api/preferences/u1")
    assert r.status_code == 200
    assert r.json() == {"preferences": ["美食"], "accommodation": "民宿", "transport": "步行"}

    r2 = client.get("/api/preferences/nobody")
    assert r2.status_code == 200
    assert r2.json() == {}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_preferences_api.py -v`
Expected: FAIL(404 / 路由不存在)

- [ ] **Step 3: 写实现 — main.py 五处改动**

(a) import:把现有那段 `from app.graph.conversation_store import (...)` 之后,新增一行:

```python
from app.graph.preferences_store import (
    init_pref_table, get_preferences, save_preferences_from_request
)
```

(b) lifespan 建表。把 `await init_table()` 那行改为两行:

```python
    await init_table()
    await init_pref_table()
```

(c) `ChatStartBody` 加字段:

```python
class ChatStartBody(BaseModel):
    request:TripRequest
    user_id: str = ""
```

(d) 新增完成时写画像的 helper(放在 `app = FastAPI(...)` 之后、路由定义附近的模块级):

```python
async def _persist_preferences(graph, config, thread_id: str) -> None:
    """行程完成时把最终 request 的 3 个偏好字段写回长期记忆。失败不影响主流程。"""
    try:
        conv = await get_conversation(thread_id)
        user_id = (conv or {}).get("user_id") or ""
        if not user_id:
            return
        state = await graph.aget_state(config)
        req = state.values.get("request")
        if req is None:
            return
        await save_preferences_from_request(user_id, req)
    except Exception:
        logger.warning("保存用户偏好失败", exc_info=True)
```

(e) `chat_start_stream`:`create_conversation` 调用加 `user_id`,并在 `on_done` 里追加写画像。把该函数体中这两处替换:

原:
```python
    await create_conversation( # 建记录
        thread_id,
        body.request.destination,
        str(body.request.start_date),
        str(body.request.end_date)
    )

    async def on_done(trip_plan:dict):
        await complete_conversation(thread_id,trip_plan)
```
改为:
```python
    await create_conversation( # 建记录
        thread_id,
        body.request.destination,
        str(body.request.start_date),
        str(body.request.end_date),
        body.user_id,
    )

    async def on_done(trip_plan:dict):
        await complete_conversation(thread_id,trip_plan)
        await _persist_preferences(graph, config, thread_id)
```

(f) `chat_resume_stream` 的 `on_done` 同样追加写画像。把:
```python
    async def on_done(trip_plan: dict):
        await complete_conversation(body.thread_id, trip_plan)
```
改为:
```python
    async def on_done(trip_plan: dict):
        await complete_conversation(body.thread_id, trip_plan)
        await _persist_preferences(graph, config, body.thread_id)
```

(g) 新增 GET 路由(放在其它 `/api/conversations` 路由附近):

```python
@app.get("/api/preferences/{user_id}")
async def get_user_preferences(user_id: str):
    """前端表单挂载时拉取:命中返回 3 字段,未命中返回 {} 让前端回退默认值。"""
    prefs = await get_preferences(user_id)
    return prefs or {}
```

- [ ] **Step 4: 跑测试确认通过 + 全量回归**

Run: `cd backend && python -m pytest tests/test_preferences_api.py -v && python -m pytest -q`
Expected: 新测试 PASS;全量无回归失败

- [ ] **Step 5: 提交**

```bash
git add backend/app/main.py backend/tests/test_preferences_api.py
git commit -m "feat: 偏好 GET 接口 + 完成时写回长期记忆"
```

---

### Task 4: 前端 user_id 工具 + api 接线

**Files:**
- Create: `frontend/src/userId.ts`
- Modify: `frontend/src/api.ts`

**Interfaces:**
- Produces:
  - `getUserId(): string`
  - `interface SavedPreferences { preferences: string[]; accommodation: string; transport: string }`
  - `getPreferences(userId: string): Promise<SavedPreferences | null>`
  - `startChatStream` 请求体附带 `user_id`

- [ ] **Step 1: 新建 `frontend/src/userId.ts`**

```ts
// 长期记忆的用户标识：首次访问生成 uuid 存 localStorage，后续复用。
const KEY = 'travel_user_id'

export function getUserId(): string {
  let id = localStorage.getItem(KEY)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(KEY, id)
  }
  return id
}
```

- [ ] **Step 2: 改 `frontend/src/api.ts`**

(a) 顶部 import 之后加:

```ts
import { getUserId } from './userId'

export interface SavedPreferences {
  preferences: string[]
  accommodation: string
  transport: string
}

export async function getPreferences(userId: string): Promise<SavedPreferences | null> {
  const resp = await fetch(`/api/preferences/${userId}`)
  if (!resp.ok) return null
  const data = await resp.json().catch(() => null)
  if (!data || Object.keys(data).length === 0) return null
  return data as SavedPreferences
}
```

(b) `startChatStream` 请求体带上 user_id。把:
```ts
export async function* startChatStream(req: TripRequest): AsyncGenerator<StreamEvent> {
  yield* streamPost('/api/chat/start-stream', { request: req })
}
```
改为:
```ts
export async function* startChatStream(req: TripRequest): AsyncGenerator<StreamEvent> {
  yield* streamPost('/api/chat/start-stream', { request: req, user_id: getUserId() })
}
```

- [ ] **Step 3: 构建验证**

Run: `cd frontend && npm run build`
Expected: 构建成功,无 TS/import 报错

- [ ] **Step 4: 提交**

```bash
git add frontend/src/userId.ts frontend/src/api.ts
git commit -m "feat: 前端 user_id 工具 + getPreferences 接口"
```

---

### Task 5: 表单挂载时按画像预选

**Files:**
- Modify: `frontend/src/views/FormView.vue`

**Interfaces:**
- Consumes: Task 4 的 `getPreferences`、`getUserId`

- [ ] **Step 1: 改 `frontend/src/views/FormView.vue` 的 `<script setup>`**

(a) 第 2 行 `import { ref, computed } from 'vue'` 改为引入 `onMounted`:

```ts
import { ref, computed, onMounted } from 'vue'
```

(b) 在 `import type { TripRequest } from '../types'` 之后加:

```ts
import { getPreferences } from '../api'
import { getUserId } from '../userId'
```

(c) 在 `buildRequest` 函数定义之后(`</script>` 之前)加挂载钩子:

```ts
// 长期记忆：有上次画像就预选 口味/住宿/交通；新用户保持静态默认值
onMounted(async () => {
  const saved = await getPreferences(getUserId())
  if (!saved) return
  if (saved.transport) transport.value = saved.transport
  if (saved.accommodation) accommodation.value = saved.accommodation
  if (saved.preferences && saved.preferences.length) {
    preferences.value = saved.preferences
  }
})
```

- [ ] **Step 2: 构建验证**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 3: 端到端手动验证**

1. 启动后端:`cd backend && uvicorn app.main:app --reload`
2. 启动前端:`cd frontend && npm run dev`
3. 浏览器打开表单页 → 跑完一次行程,口味选"美食/历史文化",住宿选"豪华型酒店",交通选"自驾",在反馈处输入"满意"结束。
4. 刷新页面重开表单 → 预期:交通=自驾、住宿=豪华型酒店、口味勾选=美食/历史文化(由 `GET /api/preferences/<id>` 返回,可在 Network 面板确认)。
5. 用浏览器隐身窗口(新 user_id)打开 → 预期:表单是静态默认值(交通=公共交通、住宿=经济型酒店、口味=自然风光),`GET` 返回 `{}`。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/FormView.vue
git commit -m "feat: 表单按上次偏好预选"
```

---

## 验收

- 后端:`cd backend && python -m pytest -q` 全绿。
- 前端:`cd frontend && npm run build` 成功。
- 端到端:Task 5 Step 3 的预选与新用户回退两条路径均符合预期。
- 偏好写入失败时(可临时把表名改错模拟),行程仍正常完成并返回(仅日志告警)。
