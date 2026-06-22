# 后端分层重构 — 设计文档

- 日期:2026-06-22
- 分支:feature-20260605-practice
- 状态:已通过设计评审,待写实现计划

## 1. 目标

让后端目录"一眼能对上职责":数据库代码、路由、图、agent 各归各位。**纯结构调整,行为零改变。**

明确**不做**(用户划定的范围外):
- 不动 `agents/`(不拆"纯领域计算 vs LLM agent")。
- 不动全局 `session`/`ctx`(`tools.py` 的 `_session_var`、`revise_tools.py` 的 `get_ctx()`)。
- 不改任何业务逻辑、不改 API 路径、不改请求/响应格式。

## 2. 现状问题(审计结论)

| # | 问题 | 涉及 |
|---|---|---|
| 1 | 空的死目录,且命名打架 | `app/api/`(空)、`app/tools/`(空,与 `agents/tools.py` 撞名) |
| 2 | 持久层放在 `graph/` 里 | `graph/conversation_store.py`、`graph/preferences_store.py` 是纯 SQLite 读写 |
| 3 | `main.py` 什么都干(204 行) | app 创建 + lifespan + 8 路由 + 完成写画像编排 + SSE |

本次范围 = 解决 1/2/3。

## 3. 目标结构

```
app/
  main.py            装配入口:load_dotenv、建 app、CORS、lifespan、include_router(~50 行)
  api/               【启用空目录】路由按域拆,每文件一个 APIRouter
    __init__.py
    chat.py            /api/chat/start-stream、resume-stream
                       （+ ChatStartBody/ChatResumeBody、SSE_HEADERS、_persist_preferences）
    conversations.py   /api/conversations 增删查 + /{id}/state + /{id}/complete
    preferences.py     /api/preferences/{user_id}
  db/                【新建】持久层从 graph/ 搬出
    __init__.py
    conversation_store.py   (原样搬,文件名不变)
    preferences_store.py    (原样搬,文件名不变)
  graph/             只剩"图"
    conversation.py  workflow.py  streaming.py
  agents/  schemas/  不动
  (删除空目录 app/tools/)
```

### 命名决定
- `db/` 内**保留 `_store` 后缀、文件名不变**,只换包路径 `graph` → `db`。理由:① import 改动最小;② `_store` 一眼看出是持久层;③ 不与 `api/conversations.py` 撞基名。
- `/api/health` 太小,留在 `main.py`,不单独建文件。
- `app/api/`、`app/db/` 需各加 `__init__.py` 成为包。

## 4. 迁移映射

| 原 | 现 | 改动类型 |
|---|---|---|
| `graph/conversation_store.py` | `db/conversation_store.py` | 纯移动 |
| `graph/preferences_store.py` | `db/preferences_store.py` | 纯移动 |
| `main.py` chat 两路由 | `api/chat.py` | 移动 + 改 graph 取法 |
| `main.py` conversations 五路由 | `api/conversations.py` | 移动 + 改 graph 取法 |
| `main.py` preferences 一路由 | `api/preferences.py` | 移动 |
| `main.py` 的 `ChatStartBody`/`ChatResumeBody`/`SSE_HEADERS`/`_persist_preferences` | `api/chat.py` | 随 chat 路由搬 |
| 空 `app/tools/` | 删除 | — |

### import 同步点(grep 已确认全集)
- `main.py`:`from app.graph.conversation_store import …` → `from app.db.conversation_store import …`(preferences 同理);移除已搬走的路由;末尾新增 `include_router`。
- 测试 3 个文件:`tests/test_conversation_store.py`、`tests/test_preferences_store.py`、`tests/test_preferences_api.py` 里 `from app.graph import …_store` → `from app.db import …_store`。
- `graph/conversation.py` 等**不 import store**,不受影响。

## 5. 路由层写法(本次唯一非机械改动)

每个 `api/*.py`:
```python
from fastapi import APIRouter, Request
router = APIRouter()
```
handler 把闭包里的 `app.state.conv_graph` 改成从 `Request` 注入:
```python
@router.post("/api/chat/start-stream")
async def chat_start_stream(body: ChatStartBody, request: Request):
    graph = request.app.state.conv_graph   # 原:闭包 app.state
    ...
```
路径保持原样(在装饰器里写全 `/api/...`,不用 prefix,避免改变现有 URL)。

`main.py` 末尾装配:
```python
from app.api import chat, conversations, preferences
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(preferences.router)
```
`_persist_preferences`(完成时写画像的编排)随 chat 路由进 `api/chat.py`。

`lifespan`、CORS、`DB_PATH`、`/api/health` 留在 `main.py`。

## 6. 风险与约束

- **`load_dotenv()` 顺序**:`main.py` 顶部 `load_dotenv()` 必须仍在所有 `from app.* import` 之前(weather.py 等模块顶层读 env)。拆出的 api 模块在 main.py 里 import,排在 `load_dotenv()` 之后即安全。
- **行为零改变**:API 路径、请求体、响应、SSE 全不变。
- **不碰** agents / 全局 session·ctx / 业务逻辑。

## 7. 验证

- **基线**:动手前 `cd backend && python -m pytest -v`,确认全绿。
- **过程**:每完成一步(搬 db → 拆 chat → 拆 conversations → 拆 preferences → 瘦身 main → 删空目录)重跑全套测试,保持全绿。
- **终态**:全部测试通过且无新增/修改的断言(除 import 路径);手动启动 `uvicorn` 确认接口可用(可选)。
- 测试本身**不新增**——本次是结构调整,现有 `test_workflow`/`test_conversation`/`test_conversation_store`/`test_preferences_store`/`test_preferences_api` 即安全网。

## 8. 未来可扩展(本期不做)

- `agents/` 拆分:纯领域计算(hotel 几何打分、attraction poi 解析、weather)归 `services/`,LLM agent 归 `agents/`。
- 消除全局 `session`/`ctx`,改为显式传参(架构级,风险较高)。
