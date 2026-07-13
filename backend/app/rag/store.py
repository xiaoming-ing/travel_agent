"""景点知识SQLite存储：按(user_id,city)隔离，按upload_id分批管理。

向量存法：float32数组 -> .tobytes()存进BLOB列；
读出来用np.frombuffer(bytes,dtype=np.float32)还原。
"""
import os
import aiosqlite
import numpy as np
import uuid
from datetime import datetime,timezone

#和其他表共用一个数据库文件
DB_PATH = os.getenv("CHECKPOINTS_DB","checkpoints.db")

async def init_knowledge_table() -> None:
    """建表+建索引(幂等，IF NOT EXISTS)。应用启动时调用一次。"""
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
        # 检索走（user_id,city);列表/删除走（user_id,upload_id)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_user_city
            ON attraction_knowledge(user_id,city)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_user_upload
            ON attraction_knowledge(user_id,upload_id)
        """)
        await db.commit()

async def add_knowledge(
    user_id:str,
    city: str,
    source: str,
    chunks: list[str],
    embeddings: np.ndarray # shape[len(chunks),512]
) -> str:
    """写一批chunk(同批共享一个upload_id),返回upload_id."""
    upload_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        for i,chunk in enumerate(chunks):
            await db.execute(
                """
                INSERT INTO attraction_knowledge
                (id,user_id,city,source,content,embedding,upload_id,created_at)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    str(uuid.uuid4()),
                    user_id,city,source,chunk,
                    embeddings[i].tobytes(),
                    upload_id,now
                )
            )
        await db.commit()
    return upload_id

async def list_uploads(user_id:str) -> list[dict]:
    """列出改用户所有上传批次(按时间倒序)，没批聚合出chunk数量。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row # 让查询结果能像字典一样按列名取
        cursor = await db.execute(
            """SELECT upload_id,city,source,
                COUNT(*) AS chunk_count,
                MIN(created_at) AS created_at
                FROM attraction_knowledge
                WHERE user_id = ?
                GROUP BY upload_id
                ORDER BY created_at DESC
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def delete_upload(user_id:str,upload_id:str) -> int:
    """删除该用户名下指定批次的所有chunk，返回删除行数。
    WHERE 同时带user_id,保证不删除别人的。
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM attraction_knowledge WHERE user_id = ? AND upload_id= ?",
            (user_id,upload_id),
        )
        await db.commit()
        return cursor.rowcount #实际删除的行数
    

async def fetch_city_chunks(user_id:str,city:str) -> list[dict]:
    """取出该用户在指定城市的全部chunk(content+embedding原始字节)。
    检索时会把这些全量拉出来，在python里算相似度。
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT content,embedding FROM attraction_knowledge WHERE user_id = ? AND city = ?",
            (user_id,city)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]