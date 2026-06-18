# 长期记忆:基于用户偏好的画像 — 设计文档

- 日期:2026-06-18
- 分支:feature-20260605-practice
- 状态:已通过设计评审,待写实现计划

## 1. 目标

让旅行助手跨对话记住用户的**旅行偏好**:下次新开行程时,表单按上次的选择自动预选,用户少填、可改。

明确**不做**(YAGNI):
- 不升级 langgraph / langgraph-checkpoint-sqlite 依赖。
- 不使用 LangGraph 官方 Store 机制(`compile(store=...)`)。
- 不做语义记忆 / 向量召回。
- 不记 `extra_requirements`(忌口/自由文本),只记 3 个结构化字段。
- 不做登录/账号体系。

## 2. 关键决策(及理由)

| 决策点 | 结论 | 理由 |
|---|---|---|
| 记什么 | 旅行偏好 | 旅行助手最自然、最可复用的长期记忆 |
| 字段 | `preferences` / `accommodation` / `transport` 三个结构化字段 | 都是勾选框/下拉,预选自然;`extra_requirements` 是自由文本,预填易带入本次专属内容(如"想看升旗") |
| 用户身份 | 前端生成 uuid 存 localStorage,随请求带上 `user_id` | 无需登录体系即可获得稳定身份做 key |
| 存储方案 | 方案 3:自建 SQLite `user_preferences` 表 + 工具函数,不走官方 Store | 用户选择不升级依赖;3 个固定字段属结构化记忆,表是对的数据模型;与现有 `conversation_store.py` 风格一致 |
| 读/应用位置 | **前端表单**:挂载时拉画像,用作默认值 | 比在对话里 interrupt 问"沿用吗"更直观;用户审表单即确认 |
| 确认方式 | 用户审阅预选好的表单(可改),提交即确认 | 无需额外的 in-chat 确认环节 |
| 写入时机 | **仅在行程完成时写一次** | 偏好在表单提交时已定死,start 与 complete 值几乎相同(双写冗余);全新用户经 `clarify_node` 兜底补的偏好,只有完成时写才能捕获到 |

> 关于"为什么不升级用官方 Store":最新 `langgraph-checkpoint-sqlite 3.1.0` 已内置官方 `AsyncSqliteStore`,升级是可行路径且代码更少。但用户明确选择**不升级依赖**,因此采用方案 3。此决策记录在案,未来若升级可平滑迁移到官方 Store(节点读写语义一致)。

## 3. 架构与数据流

```
首次访问:
  前端生成 uuid → localStorage('travel_user_id')

新开行程:
  FormView onMounted
    → GET /api/preferences/{user_id}
    → 命中:用画像预选 口味/住宿/交通(勾选框/下拉)
      未命中(新用户):沿用现有静态默认值
  用户审表单、修改、提交         ← 这一步即"确认沿用"
    → POST /api/chat/start-stream  { request, user_id }

后端规划:
  request 已携带最终偏好 → plan_node → run_workflow(request)
  规划层(景点/酒店/行程)零改动,自动吃到偏好

行程完成时(on_done 回调):
  从图状态读最终 request 的 3 个字段
  按 thread_id 查回 user_id
  UPSERT 进 user_preferences 表
```

**核心不变量:画像不进入规划代码,只合并进 `TripRequest`,下游全部复用现有逻辑。**

各字段在规划层的既有落点(无需改动):
- `preferences` → `tools.search_attractions` / `attraction.resolve_poi_types`:决定搜的地点类型
- `accommodation` → `tools.search_hotels`:酒店档次
- `transport` → `hotel.score_hotel`:打分权重与距离上限

## 4. 数据模型

新表 `user_preferences`,存于现有 `checkpoints.db`(与 `conversations` 表共用文件)。

| 列 | 类型 | 说明 |
|---|---|---|
| `user_id` | TEXT PRIMARY KEY | 前端生成的 uuid |
| `preferences` | TEXT | JSON 数组,如 `["历史文化","美食"]` |
| `accommodation` | TEXT | 如 `豪华型酒店` |
| `transport` | TEXT | 如 `公共交通` |
| `updated_at` | TEXT | ISO 时间戳 |

`conversations` 表新增一列:`user_id TEXT`(创建会话时写入,供完成时回查)。

## 5. 组件与接口

### 5.1 后端新增模块 `app/graph/preferences_store.py`

对照 `conversation_store.py` 的写法,async + aiosqlite,共用 `DB_PATH`:

- `init_pref_table() -> None`
  建表 `user_preferences`(IF NOT EXISTS)。
- `get_preferences(user_id: str) -> dict | None`
  返回 `{"preferences": list[str], "accommodation": str, "transport": str}`;无记录返回 `None`。`preferences` 列做 JSON 反序列化。
- `save_preferences(user_id, preferences: list[str], accommodation: str, transport: str) -> None`
  UPSERT(`INSERT ... ON CONFLICT(user_id) DO UPDATE`),写入 `updated_at`。

### 5.2 后端 `main.py`

- lifespan 启动时追加调用 `await init_pref_table()`。
- 新增 `GET /api/preferences/{user_id}`:返回画像 dict;未命中返回 `{}`(前端据此回退静态默认值)。
- `ChatStartBody` 增加字段 `user_id: str`。
- `chat_start_stream`:`create_conversation(...)` 传入 `user_id`。
- 完成写入:在 `on_done` 中(start 与 resume 两条流都经过),
  - `state = await graph.aget_state(config)` 取 `req = state.values["request"]`
  - 按 `thread_id` 从 `conversations` 查回 `user_id`
  - 调 `save_preferences(user_id, req.preferences, req.accommodation, req.transport)`
  - 实现注意:经 checkpointer 序列化/回读后,`request` 可能是 `TripRequest` 对象,也可能是 `dict`。取字段时需兼容两种形态(如先 `TripRequest.model_validate(req)` 归一,或对 dict/对象分别取值)。

### 5.3 后端 `conversation_store.py`

- 建表语句 `conversations` 增加列 `user_id TEXT`。
- `create_conversation(...)` 增加 `user_id` 参数并写入。

### 5.4 `clarify_node` — 不改动

现有逻辑"`preferences` 为空才 interrupt 询问"天然成为兜底:老用户表单已预选,不触发;仅全新用户、且表单未选偏好时才会问。

### 5.5 前端

- 新增 user_id 工具:读 `localStorage['travel_user_id']`,缺失则 `crypto.randomUUID()` 生成并写回。
- `api.ts`:新增 `getPreferences(userId)`;start 请求体带 `user_id`。
- `FormView.vue`:`onMounted` 调 `getPreferences`,命中则用于预选 口味/住宿/交通 三项;未命中保留现有静态默认值。

## 6. 错误处理

- `GET /api/preferences/{user_id}` 未命中:返回 `{}`,前端回退静态默认值(非错误路径)。
- 写入画像失败:记日志告警,**不**影响行程完成与返回(长期记忆是增强项,不应阻断主流程)。
- `preferences` JSON 解析失败:视作无画像,回退默认值,记日志。
- 前端拉画像失败(网络/超时):静默回退静态默认值。

## 7. 测试

- `preferences_store`:
  - 首次 `save` 后 `get` 能取回,字段与 JSON 解析正确。
  - 重复 `save` 走 UPDATE 分支(UPSERT),`updated_at` 刷新,不产生重复行。
  - `get` 未命中返回 `None`。
- API:
  - `GET /api/preferences/{user_id}` 命中返回 3 字段;未命中返回 `{}`。
  - `start-stream` 带 `user_id` 能正常建会话(`conversations.user_id` 落库)。
- 回归:现有 `test_workflow` / `test_conversation` 不受影响。

## 8. 未来可扩展(本期不做)

- 升级依赖,迁移到官方 `AsyncSqliteStore`(节点读写语义一致,迁移成本低)。
- 纳入 `extra_requirements` 中的持久约束(如忌口/过敏)——需从自由文本中抽取结构化项。
- 语义/情景记忆(向量召回)。
