# 后端分层重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把后端按职责重新分层(`db/` 持久层、`api/` 路由层、`graph/` 只留图),`main.py` 瘦身为装配入口,行为零改变。

**Architecture:** 纯结构调整。持久层从 `graph/` 搬到新建 `db/`;`main.py` 的 8 个路由按域拆进 `api/chat.py`、`api/conversations.py`、`api/preferences.py`(用 `APIRouter`);路由内 `app.state.conv_graph` 改为 `request.app.state.conv_graph`;`main.py` 末尾 `include_router`。

**Tech Stack:** FastAPI(APIRouter / Request)、LangGraph、aiosqlite、pytest。

## Global Constraints

- 测试环境:conda `graph_env`,**从 `backend/` 目录**跑,import 用 `app.` 前缀(不加 `backend.`)。
- 测试命令统一:`cd backend && python -m pytest -q`。
- `main.py` 顶部 `load_dotenv()` 必须始终在所有 `from app.* import` **之前**(weather.py 等模块顶层读 env)。
- **行为零改变**:API 路径、请求体、响应、SSE 全不变;不新增/修改测试断言(仅改 import 路径)。
- **范围外不碰**:`agents/`、全局 `session`/`ctx`、任何业务逻辑。
- 提交信息:中文 + conventional 前缀,不加 Co-Authored-By。
- 回归门:每个 Task 末尾 `python -m pytest -q` 必须 **13 passed**(基线已确认全绿)。

---

### Task 1: 持久层搬到 `db/`

**Files:**
- Create: `backend/app/db/__init__.py`(空文件)
- Move: `backend/app/graph/conversation_store.py` → `backend/app/db/conversation_store.py`
- Move: `backend/app/graph/preferences_store.py` → `backend/app/db/preferences_store.py`
- Modify: `backend/app/main.py`(2 处 import 的包路径)
- Modify: `backend/tests/test_conversation_store.py:2`、`backend/tests/test_preferences_store.py:2`、`backend/tests/test_preferences_api.py:3`

**Interfaces:**
- Produces: `app.db.conversation_store`(含 `init_table, create_conversation, complete_conversation, list_conversations, get_conversation, delete_conversation`)、`app.db.preferences_store`(含 `init_pref_table, get_preferences, save_preferences_from_request`)。文件内容不变,仅包路径从 `app.graph.*` 变为 `app.db.*`。

- [ ] **Step 1: 建包并用 git mv 搬文件(保内容不变)**

```bash
cd /Users/admin/AI/travel-agent/backend
mkdir -p app/db
touch app/db/__init__.py
git mv app/graph/conversation_store.py app/db/conversation_store.py
git mv app/graph/preferences_store.py app/db/preferences_store.py
```

- [ ] **Step 2: 改 main.py 的两处 import 包路径**

把 `app/main.py` 中:
```python
from app.graph.conversation_store import (
    init_table, create_conversation, complete_conversation,
    list_conversations, get_conversation,delete_conversation
)
from app.graph.preferences_store import (
    init_pref_table, get_preferences, save_preferences_from_request
)
```
改为(仅 `graph` → `db`):
```python
from app.db.conversation_store import (
    init_table, create_conversation, complete_conversation,
    list_conversations, get_conversation,delete_conversation
)
from app.db.preferences_store import (
    init_pref_table, get_preferences, save_preferences_from_request
)
```

- [ ] **Step 3: 改 3 个测试文件的 import 包路径**

- `tests/test_conversation_store.py:2`:`from app.graph import conversation_store as cs` → `from app.db import conversation_store as cs`
- `tests/test_preferences_store.py:2`:`from app.graph import preferences_store as ps` → `from app.db import preferences_store as ps`
- `tests/test_preferences_api.py:3`:`from app.graph import preferences_store as ps` → `from app.db import preferences_store as ps`

- [ ] **Step 4: 跑测试确认全绿**

Run: `cd backend && python -m pytest -q`
Expected: `13 passed`

- [ ] **Step 5: 提交**

```bash
cd /Users/admin/AI/travel-agent
git add -A
git commit -m "refactor: 持久层从 graph/ 搬到 db/"
```

---

### Task 2: 抽出 `api/chat.py`(开会话 / 续跑)

**Files:**
- Create: `backend/app/api/__init__.py`(空文件)
- Create: `backend/app/api/chat.py`
- Modify: `backend/app/main.py`(删除已搬走的 chat 路由、`ChatStartBody`/`ChatResumeBody`/`SSE_HEADERS`/`_persist_preferences`;新增 `include_router`)

**Interfaces:**
- Consumes:`app.graph.streaming.stream_graph`、`app.db.conversation_store.{create_conversation,complete_conversation,get_conversation}`、`app.db.preferences_store.save_preferences_from_request`。
- Produces:`app.api.chat.router`(含 `POST /api/chat/start-stream`、`POST /api/chat/resume-stream`)。

- [ ] **Step 1: 新建 `app/api/__init__.py`(空)与 `app/api/chat.py`**

`app/api/chat.py` 完整内容:
```python
"""会话相关路由:开新会话 / 续跑(均为 SSE 流式)。"""
import logging
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel

from app.schemas import TripRequest
from app.graph.streaming import stream_graph
from app.db.conversation_store import (
    create_conversation, complete_conversation, get_conversation,
)
from app.db.preferences_store import save_preferences_from_request

logger = logging.getLogger(__name__)

router = APIRouter()

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",   # 禁用可能的反代缓冲
}


class ChatStartBody(BaseModel):
    request: TripRequest
    user_id: str = ""


class ChatResumeBody(BaseModel):
    thread_id: str
    answer: str


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


@router.post("/api/chat/start-stream")
async def chat_start_stream(body: ChatStartBody, request: Request):
    """流式版开会话。客户端按SSE协议读事件。"""
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    graph = request.app.state.conv_graph

    await create_conversation(
        thread_id,
        body.request.destination,
        str(body.request.start_date),
        str(body.request.end_date),
        body.user_id,
    )

    async def on_done(trip_plan: dict):
        await complete_conversation(thread_id, trip_plan)
        await _persist_preferences(graph, config, thread_id)

    return StreamingResponse(
        stream_graph(graph, {"request": body.request}, config, on_done=on_done),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/api/chat/resume-stream")
async def chat_resume_stream(body: ChatResumeBody, request: Request):
    """流式版续跑。"""
    config = {"configurable": {"thread_id": body.thread_id}}
    graph = request.app.state.conv_graph

    async def on_done(trip_plan: dict):
        await complete_conversation(body.thread_id, trip_plan)
        await _persist_preferences(graph, config, body.thread_id)

    return StreamingResponse(
        stream_graph(graph, Command(resume=body.answer), config, on_done=on_done),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
```

- [ ] **Step 2: 从 main.py 删除已搬走的内容,并注册 router**

在 `app/main.py` 中删除:`SSE_HEADERS` 定义、`_persist_preferences` 函数、`ChatStartBody`/`ChatResumeBody` 两个类、`chat_start_stream`/`chat_resume_stream` 两个路由函数。
在 import 区(`load_dotenv()` 之后)加:`from app.api import chat`。
在 `app = FastAPI(...)` 之后加:`app.include_router(chat.router)`。
此时 main.py 仍保留 conversations / preferences / health 路由(后续 Task 处理)。注意暂时仍需要的 import(`Command`、`StreamingResponse`、`uuid`、`stream_graph` 等若仅被已删路由使用,可一并删除;`extract_interrupt`、`HTTPException`、`get_conversation` 等仍被剩余路由使用,保留)。

- [ ] **Step 3: 跑测试确认全绿**

Run: `cd backend && python -m pytest -q`
Expected: `13 passed`

- [ ] **Step 4: 提交**

```bash
cd /Users/admin/AI/travel-agent
git add -A
git commit -m "refactor: chat 路由抽到 api/chat.py"
```

---

### Task 3: 抽出 `api/conversations.py`(历史对话)

**Files:**
- Create: `backend/app/api/conversations.py`
- Modify: `backend/app/main.py`(删除 5 个 conversations 路由;新增 `include_router`)

**Interfaces:**
- Consumes:`app.graph.streaming.extract_interrupt`、`app.db.conversation_store.{list_conversations,get_conversation,delete_conversation,complete_conversation}`。
- Produces:`app.api.conversations.router`(含 `GET /api/conversations`、`GET /api/conversations/{thread_id}`、`DELETE /api/conversations/{thread_id}`、`GET /api/conversations/{thread_id}/state`、`POST /api/conversations/{thread_id}/complete`)。

- [ ] **Step 1: 新建 `app/api/conversations.py`**

完整内容:
```python
"""历史对话相关路由:列表 / 详情 / 删除 / 实时状态 / 标记完成。"""
from fastapi import APIRouter, Request, HTTPException

from app.graph.streaming import extract_interrupt
from app.db.conversation_store import (
    list_conversations, get_conversation, delete_conversation, complete_conversation,
)

router = APIRouter()


@router.get("/api/conversations")
async def get_conversations():
    return await list_conversations()


@router.get("/api/conversations/{thread_id}")
async def get_one_conversation(thread_id: str):
    conv = await get_conversation(thread_id)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conv


@router.delete("/api/conversations/{thread_id}")
async def delete_one_conversation(thread_id: str):
    success = await delete_conversation(thread_id)
    if not success:
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"ok": True, "messages": "删除成功"}


@router.get("/api/conversations/{thread_id}/state")
async def get_conv_state(thread_id: str, request: Request):
    """查对话的实时状态：有 interrupt → 进行中，有 trip_plan → 已完成"""
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = await request.app.state.conv_graph.aget_state(config)
    except Exception:
        raise HTTPException(status_code=404, detail="对话不存在")

    interrupt_payload = extract_interrupt(state)
    if interrupt_payload:
        return {
            "status": "need_input",
            "question": interrupt_payload.get("question"),
            "trip_plan": interrupt_payload.get("trip_plan"),
        }

    trip_plan = state.values.get("trip_plan")
    if trip_plan:
        return {"status": "done", "trip_plan": trip_plan}

    return {"status": "unknown"}


@router.post("/api/conversations/{thread_id}/complete")
async def mark_conversation_complete(thread_id: str, request: Request):
    """用户直接点'查看完整行程'时调用，把对话标记为 done。"""
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = await request.app.state.conv_graph.aget_state(config)
        trip_plan = state.values.get("trip_plan")
        if trip_plan:
            await complete_conversation(thread_id, trip_plan)
            return {"ok": True}
        return {"ok": False, "reason": "no trip_plan"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 2: 从 main.py 删 5 个 conversations 路由,注册 router**

删除 `get_conversations`、`get_one_conversation`、`delete_one_conversation`、`get_conv_state`、`mark_conversation_complete`。
import 区加 `conversations`:`from app.api import chat, conversations`。
注册:`app.include_router(conversations.router)`。
此时 main.py 已不再直接用 `extract_interrupt`,可删该 import;`get_conversation`/`complete_conversation` 等若不再被 main 使用也删。

- [ ] **Step 3: 跑测试确认全绿**

Run: `cd backend && python -m pytest -q`
Expected: `13 passed`

- [ ] **Step 4: 提交**

```bash
cd /Users/admin/AI/travel-agent
git add -A
git commit -m "refactor: conversations 路由抽到 api/conversations.py"
```

---

### Task 4: 抽出 `api/preferences.py`

**Files:**
- Create: `backend/app/api/preferences.py`
- Modify: `backend/app/main.py`(删除 preferences 路由;新增 `include_router`)

**Interfaces:**
- Consumes:`app.db.preferences_store.get_preferences`。
- Produces:`app.api.preferences.router`(含 `GET /api/preferences/{user_id}`)。

- [ ] **Step 1: 新建 `app/api/preferences.py`**

完整内容:
```python
"""长期记忆:按 user_id 读取偏好画像,供前端表单预选。"""
from fastapi import APIRouter

from app.db.preferences_store import get_preferences

router = APIRouter()


@router.get("/api/preferences/{user_id}")
async def get_user_preferences(user_id: str):
    """前端表单挂载时拉取:命中返回 3 字段,未命中返回 {} 让前端回退默认值。"""
    prefs = await get_preferences(user_id)
    return prefs or {}
```

- [ ] **Step 2: 从 main.py 删 preferences 路由,注册 router**

删除 `get_user_preferences`。
import 区:`from app.api import chat, conversations, preferences`。
注册:`app.include_router(preferences.router)`。
main.py 此时已不再直接用 `get_preferences`,删该 import。

- [ ] **Step 3: 跑测试确认全绿**

Run: `cd backend && python -m pytest -q`
Expected: `13 passed`

- [ ] **Step 4: 提交**

```bash
cd /Users/admin/AI/travel-agent
git add -A
git commit -m "refactor: preferences 路由抽到 api/preferences.py"
```

---

### Task 5: main.py 收尾 + 删空目录

**Files:**
- Modify: `backend/app/main.py`(整理为装配入口的最终形态)
- Delete: `backend/app/tools/`(空目录)

**Interfaces:**
- Produces:`app.main.app`(FastAPI 实例,装配三 router + health + lifespan)。

- [ ] **Step 1: 把 main.py 整理为最终形态**

`app/main.py` 完整目标内容:
```python
from dotenv import load_dotenv
load_dotenv()  # 必须在任何 app.* import 之前，否则 weather.py 等模块顶部 os.getenv 拿不到 .env 里的值

import logging
import os

# 日志级别由环境变量控制：生产设 INFO/WARNING，开发设 DEBUG
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.graph.conversation import build_conversation_builder
from app.db.conversation_store import init_table
from app.db.preferences_store import init_pref_table
from app.api import chat, conversations, preferences

DB_PATH = os.getenv("CHECKPOINTS_DB", "checkpoints.db")


# 应用生命周期：启动时打开 SQLite 连接 + 编译 conversation graph;结束时关闭
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_table()
    await init_pref_table()
    async with AsyncSqliteSaver.from_conn_string(DB_PATH) as checkpointer:
        app.state.conv_graph = build_conversation_builder().compile(checkpointer=checkpointer)
        logger.info("conversation graph 已就绪，checkpoints.db 已连接")
        yield
    logger.info("checkpoints.db 已关闭")


app = FastAPI(title="旅行智能助手", lifespan=lifespan)

_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")

# 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(preferences.router)


@app.get("/api/health")
async def heath():
    return {"status": "ok"}
```

- [ ] **Step 2: 删除空目录 app/tools/**

```bash
cd /Users/admin/AI/travel-agent/backend
rmdir app/tools
```
(若 `app/tools/` 下有 `__pycache__` 残留,先 `rm -rf app/tools/__pycache__` 再 `rmdir`。)

- [ ] **Step 3: 跑测试确认全绿**

Run: `cd backend && python -m pytest -q`
Expected: `13 passed`

- [ ] **Step 4: 冒烟验证 app 能正常装配(可选但推荐)**

Run: `cd backend && python -c "from app.main import app; print(sorted(r.path for r in app.routes if getattr(r,'path','').startswith('/api')))"`
Expected: 打印出全部 9 条 `/api/...` 路径(chat 2 + conversations 5 + preferences 1 + health 1),无 import 报错。

- [ ] **Step 5: 提交**

```bash
cd /Users/admin/AI/travel-agent
git add -A
git commit -m "refactor: main.py 瘦身为装配入口 + 删除空目录"
```

---

## 验证总览

- 每个 Task 末尾 `cd backend && python -m pytest -q` 必须 `13 passed`。
- 终态目录:`app/{main.py, api/, db/, graph/, agents/, schemas/}`,无 `app/tools/`。
- `graph/` 只剩 `conversation.py / workflow.py / streaming.py`。
- API 路径、请求/响应、SSE 全部不变。
