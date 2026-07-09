# 景点描述知识库:用户上传攻略的 RAG 检索 — 设计文档

- 日期:2026-07-09
- 状态:已通过设计评审,待写实现计划

## 1. 目标

让用户上传城市攻略/游记等**非结构化长文本**,系统自动分块、向量化并存库;生成行程时,按候选景点名从用户自己的知识库检索相关段落,作为【参考资料】注入 Phase 2 行程生成提示,使景点 `description` 有真实资料支撑,而非 LLM 凭空编造。

**背景问题**:高德 POI 只返回名字/地址/坐标/图片,**没有景点描述**。当前 `Attraction.description` 由 Phase 2 的 itinerary LLM 自行生成([itinerary.py:38](../../../backend/app/agents/itinerary.py)),是幻觉的主要来源。

明确**不做**(YAGNI):
- 不引入专业向量库(Chroma/FAISS/pgvector),用 SQLite 存向量、Python 算余弦即可。
- 不做知识库的编辑/更新(只支持上传新批次 + 删除整批)。
- 不做跨用户共享(严格按用户隔离)。
- 不改 Phase 1 的工具集(检索发生在 Phase 2 生成前,不作为 Agent 工具)。
- 不做增量重嵌入 / 模型版本迁移。
- 不做 OCR / 文件上传,只接受粘贴的纯文本。

## 2. 关键决策(及理由)

| 决策点 | 结论 | 理由 |
|---|---|---|
| 上传形态 | 非结构化长文本(城市级攻略) | 输入最自由,一篇攻略可涵盖多个景点;走真 RAG 分块+检索链路 |
| 向量方案 | 本地 `sentence-transformers` 嵌入 + SQLite 存向量 | 无新中间件,与现有纯 SQLite 架构一致;数据量小,全量加载算余弦足够 |
| 嵌入模型 | `BAAI/bge-small-zh-v1.5`(512 维,~95MB) | 中文检索效果好、体积小、可本地跑;懒加载单例 |
| 注入点 | Phase 2 `generate_plan` 生成前,拼进 `ITINERARY_PROMPT` | 改动集中;描述和选景倾向都能受益;幻觉最好控 |
| 作用域 | 按 `(user_id, city)` 隔离 | 每人只检索到自己上传的资料,符合真实产品的数据权限模型 |
| user_id 穿透 | 走 **config 通道**(`configurable.user_id`),不进图 state | `plan_node` 本就收 `config`;不污染 `ConversationState`;与现有 `thread_id` 同管道 |
| 检索策略 | 混合检索:子串命中加权 + 余弦相似度 | 景点名多为专有名词、常在原文出现,子串信号强;纯向量对"短名 vs 长段"偏弱 |
| 前端 | 新增「我的攻略库」页:上传 + 列表 + 删除 | 用户能看到/管理自己传了什么,闭环完整 |
| 降级 | 检索不到 / 模型加载失败 → 跳过,走原自动生成 | RAG 是纯增量,永不阻断主流程 |

## 3. 架构与数据流

**写入侧(用户上传攻略)**
```
「攻略库」页填:城市 + 标题 + 长文本
  → POST /api/knowledge  { city, source, content }   (JWT 鉴权取 user_id)
  → chunk_text:RecursiveCharacterTextSplitter(中文分隔符,~300 字/块,50 重叠)
  → embed_texts:sentence-transformers 批量编码每个 chunk
  → store.add:写入 attraction_knowledge,一次上传的多个 chunk 共享 upload_id
```

**读取侧(生成行程时自动检索)**
```
Phase 1 收集到候选景点(Attraction 列表,含名字)
  → Phase 2 generate_plan 前:
      retrieve_for_attractions(user_id, city, [景点名...])
        对每个景点名:
          取 (user_id, city) 下所有 chunk(数据量小,全量加载)
          score = 余弦(景点名向量, chunk向量) + 子串命中加权
          取超阈值的 Top-k 段落
      → { 景点名: [命中段落...] }
  → 命中段落作为【参考资料】拼进 ITINERARY_PROMPT
  → LLM:"有参考资料就基于它写 description,不许编造;无则照常"
  → 无命中景点 → 退回现有自动生成(优雅降级)
```

**核心不变量:RAG 只影响 `description` 的资料来源与选景倾向,不改变 TripPlan 结构、坐标解析、酒店打分等既有逻辑。检索失败时行为与现在完全一致。**

## 4. 数据模型

新表 `attraction_knowledge`,存于现有 `checkpoints.db`(与 `conversations`/`user_preferences` 共用文件)。

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PRIMARY KEY | chunk 唯一 id(uuid) |
| `user_id` | TEXT NOT NULL | 上传者,检索隔离键 |
| `city` | TEXT NOT NULL | 城市,检索隔离键 |
| `source` | TEXT | 用户填的标题/来源(如"小红书-南京三日游") |
| `content` | TEXT NOT NULL | 分块后的正文段落 |
| `embedding` | BLOB | 向量,`float32` 数组序列化(`np.tobytes()`) |
| `upload_id` | TEXT NOT NULL | 同一次上传的所有 chunk 共享,用于按批列表/删除 |
| `created_at` | TEXT NOT NULL | ISO 时间戳 |

索引:`(user_id, city)`(检索路径)、`(user_id, upload_id)`(列表/删除路径)。

> 向量存 `BLOB`(`float32.tobytes()`)比 JSON 字符串省空间、反序列化快;检索时 `np.frombuffer` 还原。

## 5. 组件与接口

### 5.1 后端新增模块 `app/rag/`

| 文件 | 职责 | 接口 |
|---|---|---|
| `embedding.py` | 懒加载嵌入模型单例,批量编码 | `embed_texts(texts: list[str]) -> np.ndarray`<br>`embed_query(text: str) -> np.ndarray` |
| `chunking.py` | 中文长文本分块 | `chunk_text(text: str) -> list[str]` |
| `store.py` | SQLite 数据访问层 | `init_table()`、`add(user_id, city, source, chunks, embeddings) -> upload_id`、`list_uploads(user_id) -> list`、`delete_upload(user_id, upload_id)`、`fetch_city_chunks(user_id, city) -> list` |
| `retriever.py` | 混合检索编排,Python 算余弦 | `retrieve_for_attractions(user_id, city, names, top_k=3, threshold=0.35) -> dict[str, list[str]]` |

**嵌入器可注入**:`embedding.py` 暴露一个可替换的编码函数入口,测试用 stub 假向量(固定维度、确定值),不下载/加载真模型。检索与分块的单测因此无需真实模型即可运行。

### 5.2 后端新增 API `app/api/knowledge.py`

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/knowledge` | body `{city, source, content}`;分块→嵌入→入库;返回 `{upload_id, chunk_count}` |
| GET | `/api/knowledge` | 返回当前用户所有上传批次(city/source/chunk 数/时间) |
| DELETE | `/api/knowledge/{upload_id}` | 删除该用户名下这一批 chunk |

- 均复用现有 JWT 鉴权(`Depends` 取 `user_id`),与 `preferences.py` 一致。
- 嵌入是 CPU 密集,POST 内用 `asyncio.to_thread` 包裹 `embed_texts`,不阻塞事件循环。
- 在 `main.py` 装配阶段调用 `store.init_table()` 建表(与现有表初始化并列)。

### 5.3 现有代码改动(user_id 穿透管道)

| 文件 | 改动 |
|---|---|
| [api/chat.py](../../../backend/app/api/chat.py) | `config` 增 `user_id`:`{"configurable": {"thread_id", "user_id"}}`;start 与 resume 均改 |
| [graph/conversation.py](../../../backend/app/graph/conversation.py) | `plan_node(state, config)` 从 `config["configurable"]["user_id"]` 读取,传入 `run_workflow` |
| [graph/workflow.py](../../../backend/app/graph/workflow.py) | `run_workflow` 新增 `user_id` 参数,透传给 `generate_plan` |
| [agents/itinerary.py](../../../backend/app/agents/itinerary.py) | `generate_plan` 新增 `user_id`;生成前检索;`_format_attractions` 拼入【参考资料】;prompt 加"有资料基于资料写、无资料照常"规则 |

> user_id 走 config 而非 state:`ConversationState` 保持不变,避免 checkpoint schema 变动;config 是 LangGraph 官方推荐的"运行时上下文"通道,与 `thread_id` 同源。

### 5.4 前端新增

| 文件 | 职责 |
|---|---|
| `src/api/knowledge.ts` | 上传/列表/删除三个接口封装 |
| `src/views/KnowledgeView.vue` | 「我的攻略库」页:城市+标题+文本框上传;下方列表展示已上传批次,支持删除 |
| `src/router/index.ts` | 新增路由 `/knowledge` |
| 导航入口 | 在现有导航加「攻略库」入口 |

## 6. 混合检索策略(核心逻辑)

对每个候选景点名 `name`:

1. 取该 `(user_id, city)` 下全部 chunk 及其向量(数据量小,一次性加载)。
2. 计算 `cos = 余弦相似度(embed_query(name), chunk_embedding)`。
3. **子串加权**:若 `name in chunk.content`,`score = cos + BONUS`(如 +0.3);否则 `score = cos`。
4. 过滤 `score >= threshold`,按 score 降序取 Top-k。
5. 汇总为 `{name: [chunk_content...]}`;无命中的 name 不出现在结果里。

> 景点名通常是专有名词、在攻略原文中原样出现,子串是强信号;纯向量对"短查询 vs 长文档"方向性偏弱。二者结合是工业界"混合检索"的入门实践,也是本功能最具学习价值的部分。

## 7. 提示注入(Phase 2)

`_format_attractions` 输出在原有 `- 名字(地址)` 基础上,对有命中的景点追加:
```
- 鸡鸣寺(南京市玄武区鸡鸣寺路1号)
    【参考资料】南朝四百八十寺之首,春季樱花大道…(命中段落,截断到 N 字)
```

`ITINERARY_PROMPT` 第 2 条(生成 description)增加规则:
> 若某景点带有【参考资料】,description 必须基于参考资料提炼,不得编造与资料矛盾的内容;无【参考资料】的景点,按你的常识简要生成。

## 8. 错误处理与降级

| 场景 | 行为 |
|---|---|
| 用户无上传 / 该城市无资料 | 检索返回空,prompt 无【参考资料】,走现有自动生成 |
| 嵌入模型加载失败 | 记 warning,`retrieve_for_attractions` 直接返回空,不阻断规划 |
| 检索过程异常 | try/except 包裹,降级为空结果 |
| 上传文本过短(不足一块) | 作为单个 chunk 存入 |
| 上传时嵌入失败 | 返回 5xx + 明确错误,不写入半份数据(先嵌入成功再落库) |

**总原则:RAG 是纯增量能力,任何失败都退回"当前已上线"的行为。**

## 9. 测试计划

- `chunk_text`:长文本切分数量、重叠、中文分隔符生效。
- 余弦相似度纯函数:正交=0、同向=1、量级无关。
- 混合检索排序:构造 stub 向量,验证"子串命中的段落排在纯向量命中之前"、阈值过滤、Top-k 截断。
- `store` 往返:add → list_uploads → fetch_city_chunks → delete_upload,验证按 user_id/city/upload_id 正确隔离。
- 嵌入器全程用 stub 注入,单测不下载真实模型。

## 10. 依赖

`requirements.txt` 已含 `sentence-transformers` 与 `langchain-text-splitters`,`numpy`(2.4.x)由 `sentence-transformers` 间接带入、已在环境中可用,无需新增依赖。仅需首次运行时下载嵌入模型权重(~95MB),部署文档需补充说明。

## 11. 交付顺序(供实现计划参考)

1. `app/rag/`(embedding / chunking / store / retriever)+ 单测(stub 嵌入器)
2. `app/api/knowledge.py` + `main.py` 建表装配
3. user_id 穿透管道(chat → conversation → workflow → itinerary)
4. Phase 2 提示注入
5. 前端「攻略库」页 + 路由 + 导航
6. 端到端联调 + 部署文档补充(模型下载说明)
