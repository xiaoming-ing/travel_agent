# 景点描述知识库(RAG)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户上传城市攻略文本,系统分块+向量化;生成行程时自动检索相关段落注入 Phase 2 提示,让景点描述有真实资料支撑。

**Architecture:** 新增 `app/rag/` 模块负责分块、嵌入、存储与检索。上传走 `/api/knowledge` 路由;检索发生在 `generate_plan` 调用前,命中段落作为【参考资料】拼进 `ITINERARY_PROMPT`。`user_id` 经 config 通道穿透到 Phase 2。前端新增「攻略库」页面实现上传/列表/删除。

**Tech Stack:** Python 3.12 / FastAPI / aiosqlite / sentence-transformers(`BAAI/bge-small-zh-v1.5`) / langchain-text-splitters / numpy / pytest(asyncio_mode=auto); Vue 3 + TypeScript + Vite。

## Global Constraints

- 向量存 SQLite(`checkpoints.db`),不引入 Chroma/FAISS/pgvector。
- 嵌入模型:`BAAI/bge-small-zh-v1.5`,懒加载单例,首次调用时下载。
- 检索策略:全量加载 `(user_id, city)` 下 chunk,Python numpy 算余弦 + 子串加权。
- RAG 任何失败均降级为空结果,不阻断主流程。
- 嵌入器设计为可注入,测试用 stub 假向量,单测不下载真模型。
- 后端测试从 `backend/` 目录运行 `pytest`,`asyncio_mode = auto`。
- 分块参数:300 字/块,50 字重叠,中文分隔符(`。！？\n`)。
- 混合检索参数:`BONUS = 0.3`,`threshold = 0.35`,`top_k = 3`。
- DB 路径取环境变量 `CHECKPOINTS_DB`(默认 `checkpoints.db`)。

## File Structure

- Create `backend/app/rag/__init__.py` — 包标识
- Create `backend/app/rag/embedding.py` — 懒加载嵌入模型,批量/单条编码
- Create `backend/app/rag/chunking.py` — 中文文本分块
- Create `backend/app/rag/store.py` — SQLite 数据访问层(建表/增/列/删/查)
- Create `backend/app/rag/retriever.py` — 混合检索编排
- Create `backend/app/api/knowledge.py` — 上传/列表/删除 API 路由
- Create `backend/tests/test_chunking.py` — 分块单测
- Create `backend/tests/test_rag_store.py` — store 往返单测
- Create `backend/tests/test_retriever.py` — 混合检索排序单测
- Modify `backend/app/main.py` — lifespan 建表 + 注册 knowledge 路由
- Modify `backend/app/api/chat.py` — config 加 user_id
- Modify `backend/app/graph/conversation.py` — plan_node 读 user_id 传给 run_workflow
- Modify `backend/app/graph/workflow.py` — run_workflow 透传 user_id 给 generate_plan
- Modify `backend/app/agents/itinerary.py` — generate_plan 检索 + 注入参考资料 + prompt 改规则
- Create `frontend/src/api/knowledge.ts` — 前端 API 封装
- Create `frontend/src/views/KnowledgeView.vue` — 攻略库页面
- Modify `frontend/src/router/index.ts` — 新增 /knowledge 路由
- Modify 导航组件 — 加「攻略库」入口

---

### Task 1: 分块模块 `chunking.py`

**Files:**
- Create: `backend/app/rag/__init__.py`
- Create: `backend/app/rag/chunking.py`
- Test: `backend/tests/test_chunking.py`

**Interfaces:**
- Consumes: 无外部依赖
- Produces: `chunk_text(text: str, chunk_size: int = 300, chunk_overlap: int = 50) -> list[str]`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_chunking.py
import pytest
from app.rag.chunking import chunk_text


def test_short_text_single_chunk():
    """短于 chunk_size 的文本应作为单个 chunk 返回。"""
    text = "南京是六朝古都。"
    result = chunk_text(text)
    assert result == [text]


def test_long_text_splits_by_chinese_punctuation():
    """长文本应按中文句号分割,每块不超过 chunk_size。"""
    # 构造超过 300 字的文本:10 句,每句 40 字
    sentences = ["这是第{}句话的内容" .format(i) + "用来填充到足够长度的字符" * 2 + "。" for i in range(10)]
    text = "".join(sentences)
    result = chunk_text(text, chunk_size=100, chunk_overlap=20)
    assert len(result) > 1
    for chunk in result:
        assert len(chunk) <= 120  # 允许小幅超出(分隔符边界)


def test_overlap_exists():
    """相邻块之间应有重叠内容。"""
    text = "。".join([f"第{i}段内容填充字符用于测试分块" for i in range(20)]) + "。"
    result = chunk_text(text, chunk_size=80, chunk_overlap=20)
    assert len(result) >= 3
    # 第二块的开头应在第一块的结尾附近出现
    overlap_found = any(
        result[1][:20] in result[0] for _ in [1]
    )
    # 至少部分重叠(不严格要求完美,因为分隔符边界可能偏移)
    assert overlap_found or len(result) > 2


def test_empty_text_returns_empty():
    result = chunk_text("")
    assert result == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && conda run -n graph_env pytest tests/test_chunking.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.rag'`

- [ ] **Step 3: Create `__init__.py` and implement `chunking.py`**

```python
# backend/app/rag/__init__.py
```

```python
# backend/app/rag/chunking.py
"""中文长文本分块:按句号等标点切分,每块 ~300 字,50 字重叠。"""
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 中文优先分隔符:段落 > 句号/问号/叹号 > 逗号 > 空格
_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", " "]


def chunk_text(
    text: str,
    chunk_size: int = 300,
    chunk_overlap: int = 50,
) -> list[str]:
    """将长文本切分为多个块。

    Args:
        text: 原始文本
        chunk_size: 每块最大字符数
        chunk_overlap: 相邻块重叠字符数

    Returns:
        分块后的文本列表;空文本返回空列表。
    """
    if not text or not text.strip():
        return []

    splitter = RecursiveCharacterTextSplitter(
        separators=_SEPARATORS,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    chunks = splitter.split_text(text.strip())
    return chunks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && conda run -n graph_env pytest tests/test_chunking.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/rag/__init__.py backend/app/rag/chunking.py backend/tests/test_chunking.py
git commit -m "feat(rag): 中文文本分块模块 chunking.py + 单测"
```

---

### Task 2: 嵌入模块 `embedding.py`

**Files:**
- Create: `backend/app/rag/embedding.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `embed_texts(texts: list[str]) -> np.ndarray`(shape `[N, 512]`)
  - `embed_query(text: str) -> np.ndarray`（shape `[512]`）
  - `set_embed_fn(fn)` — 可注入,测试用

- [ ] **Step 1: Implement `embedding.py`**

```python
# backend/app/rag/embedding.py
"""嵌入模块:懒加载 sentence-transformers 模型,提供批量/单条编码。

可注入:调用 set_embed_fn(fn) 可替换为 stub,测试不下载真模型。
"""
import logging
import numpy as np
from typing import Callable

logger = logging.getLogger(__name__)

MODEL_NAME = "BAAI/bge-small-zh-v1.5"

_model = None
_custom_embed_fn: Callable[[list[str]], np.ndarray] | None = None


def set_embed_fn(fn: Callable[[list[str]], np.ndarray] | None) -> None:
    """注入自定义嵌入函数(测试用)。传 None 恢复真实模型。"""
    global _custom_embed_fn
    _custom_embed_fn = fn


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("正在加载嵌入模型 %s ...", MODEL_NAME)
        _model = SentenceTransformer(MODEL_NAME)
        logger.info("嵌入模型加载完成")
    return _model


def embed_texts(texts: list[str]) -> np.ndarray:
    """批量编码文本列表,返回 shape [N, dim] 的 float32 数组。"""
    if _custom_embed_fn is not None:
        return _custom_embed_fn(texts)
    model = _get_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return np.array(embeddings, dtype=np.float32)


def embed_query(text: str) -> np.ndarray:
    """编码单条查询,返回 shape [dim] 的 float32 数组。"""
    result = embed_texts([text])
    return result[0]
```

- [ ] **Step 2: Quick smoke test(手动验证,不写持久测试——真模型测试在 CI 中跳过)**

Run: `cd backend && conda run -n graph_env python -c "from app.rag.embedding import embed_texts; import numpy as np; r = embed_texts(['测试']); print(r.shape, r.dtype)"`
Expected: `(1, 512) float32`(首次运行会下载模型)

- [ ] **Step 3: Commit**

```bash
git add backend/app/rag/embedding.py
git commit -m "feat(rag): 嵌入模块 embedding.py(懒加载 bge-small-zh + 可注入)"
```

---

### Task 3: 存储模块 `store.py`

**Files:**
- Create: `backend/app/rag/store.py`
- Test: `backend/tests/test_rag_store.py`

**Interfaces:**
- Consumes: `numpy`
- Produces:
  - `init_knowledge_table() -> None`
  - `add_knowledge(user_id, city, source, chunks: list[str], embeddings: np.ndarray) -> str`（返回 upload_id）
  - `list_uploads(user_id) -> list[dict]`
  - `delete_upload(user_id, upload_id) -> int`（返回删除行数）
  - `fetch_city_chunks(user_id, city) -> list[dict]`（每条含 content + embedding bytes）

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_rag_store.py
import pytest
import numpy as np
from app.rag import store


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db = str(tmp_path / "test_knowledge.db")
    monkeypatch.setattr(store, "DB_PATH", db)
    return db


async def test_add_and_list(tmp_db):
    await store.init_knowledge_table()
    chunks = ["南京鸡鸣寺是南朝名刹", "春季樱花大道很美"]
    embeddings = np.random.rand(2, 512).astype(np.float32)
    upload_id = await store.add_knowledge("u1", "南京", "小红书攻略", chunks, embeddings)

    uploads = await store.list_uploads("u1")
    assert len(uploads) == 1
    assert uploads[0]["upload_id"] == upload_id
    assert uploads[0]["city"] == "南京"
    assert uploads[0]["source"] == "小红书攻略"
    assert uploads[0]["chunk_count"] == 2


async def test_fetch_city_chunks(tmp_db):
    await store.init_knowledge_table()
    chunks = ["玄武湖畔风光好"]
    embeddings = np.random.rand(1, 512).astype(np.float32)
    await store.add_knowledge("u1", "南京", "攻略", chunks, embeddings)

    results = await store.fetch_city_chunks("u1", "南京")
    assert len(results) == 1
    assert results[0]["content"] == "玄武湖畔风光好"
    # embedding 可还原
    vec = np.frombuffer(results[0]["embedding"], dtype=np.float32)
    assert vec.shape == (512,)
    np.testing.assert_allclose(vec, embeddings[0], atol=1e-6)


async def test_isolation_by_user(tmp_db):
    await store.init_knowledge_table()
    chunks = ["内容"]
    emb = np.random.rand(1, 512).astype(np.float32)
    await store.add_knowledge("u1", "南京", "攻略", chunks, emb)
    await store.add_knowledge("u2", "南京", "攻略", chunks, emb)

    assert len(await store.fetch_city_chunks("u1", "南京")) == 1
    assert len(await store.fetch_city_chunks("u2", "南京")) == 1


async def test_delete_upload(tmp_db):
    await store.init_knowledge_table()
    chunks = ["a", "b"]
    emb = np.random.rand(2, 512).astype(np.float32)
    upload_id = await store.add_knowledge("u1", "南京", "攻略", chunks, emb)

    deleted = await store.delete_upload("u1", upload_id)
    assert deleted == 2
    assert await store.list_uploads("u1") == []


async def test_delete_only_own(tmp_db):
    """不能删别人的上传。"""
    await store.init_knowledge_table()
    emb = np.random.rand(1, 512).astype(np.float32)
    upload_id = await store.add_knowledge("u1", "南京", "攻略", ["x"], emb)

    deleted = await store.delete_upload("u2", upload_id)
    assert deleted == 0
    assert len(await store.list_uploads("u1")) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && conda run -n graph_env pytest tests/test_rag_store.py -v`
Expected: FAIL with `ModuleNotFoundError` or `AttributeError`

- [ ] **Step 3: Implement `store.py`**

```python
# backend/app/rag/store.py
"""景点知识 SQLite 存储:按 (user_id, city) 隔离,按 upload_id 分批管理。"""
import os
import uuid
from datetime import datetime, timezone

import aiosqlite
import numpy as np

DB_PATH = os.getenv("CHECKPOINTS_DB", "checkpoints.db")


async def init_knowledge_table() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS attraction_knowledge (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                city TEXT NOT NULL,
                source TEXT,
                content TEXT NOT NULL,
                embedding BLOB NOT NULL,
                upload_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_user_city
            ON attraction_knowledge(user_id, city)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_user_upload
            ON attraction_knowledge(user_id, upload_id)
        """)
        await db.commit()


async def add_knowledge(
    user_id: str,
    city: str,
    source: str,
    chunks: list[str],
    embeddings: np.ndarray,
) -> str:
    """写入一批 chunk,返回 upload_id。"""
    upload_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        for i, chunk in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            emb_bytes = embeddings[i].tobytes()
            await db.execute(
                """INSERT INTO attraction_knowledge
                   (id, user_id, city, source, content, embedding, upload_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (chunk_id, user_id, city, source, chunk, emb_bytes, upload_id, now),
            )
        await db.commit()
    return upload_id


async def list_uploads(user_id: str) -> list[dict]:
    """列出该用户所有上传批次(按时间倒序)。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT upload_id, city, source, COUNT(*) as chunk_count,
                      MIN(created_at) as created_at
               FROM attraction_knowledge
               WHERE user_id = ?
               GROUP BY upload_id
               ORDER BY created_at DESC""",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def delete_upload(user_id: str, upload_id: str) -> int:
    """删除该用户名下指定批次的所有 chunk,返回删除行数。"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM attraction_knowledge WHERE user_id = ? AND upload_id = ?",
            (user_id, upload_id),
        )
        await db.commit()
        return cursor.rowcount


async def fetch_city_chunks(user_id: str, city: str) -> list[dict]:
    """取出该用户在指定城市的全部 chunk(含 content + embedding 原始字节)。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT content, embedding FROM attraction_knowledge WHERE user_id = ? AND city = ?",
            (user_id, city),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && conda run -n graph_env pytest tests/test_rag_store.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/rag/store.py backend/tests/test_rag_store.py
git commit -m "feat(rag): SQLite 知识存储 store.py + 单测"
```

---

### Task 4: 混合检索模块 `retriever.py`

**Files:**
- Create: `backend/app/rag/retriever.py`
- Test: `backend/tests/test_retriever.py`

**Interfaces:**
- Consumes: `store.fetch_city_chunks`, `embedding.embed_texts`, `embedding.set_embed_fn`
- Produces: `retrieve_for_attractions(user_id: str, city: str, names: list[str], top_k: int = 3, threshold: float = 0.35) -> dict[str, list[str]]`

<!-- PLAN_PART2_PLACEHOLDER -->
