"""
conversations 表: 存对话元数据（标题/状态/行程结果）
和LanGraph 的 checkpoints 表共用一个 SQLite文件。
"""
import os
import aiosqlite
from datetime import datetime
import json

DB_PATH = os.getenv("CHECKPOINTS_DB","checkpoints.db")

async def init_table() -> None: # None 没有返回值
    async with aiosqlite.connect(DB_PATH) as db: # 连接数据库，aiosqlite是SQLite的异步版本
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                thread_id TEXT PRIMARY KEY,
                title TEXT,
                destination TEXT,
                create_at TEXT,
                status TEXT DEFAULT 'active',
                trip_plan TEXT
            )
            """)
        await db.commit()


async def create_conversation(
    thread_id: str,destination: str, start_date: str,end_date:str
) -> None:
    title = f"{destination}{start_date} ~ {end_date}"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO conversations"
            "(thread_id,title,destination,create_at) VALUES (?,?,?,?)",
            (thread_id,title,destination,datetime.now().isoformat())
        )
        await db.commit()

async def complete_conversation(thread_id:str,trip_plan:dict) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE conversations SET status='done',trip_plan=? WHERE thread_id=?",
            (json.dumps(trip_plan,ensure_ascii=False),thread_id)
        )
        await db.commit()

async def list_conversations(limit:int = 30) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row # 可以像dict一样访问
        async with db.execute(
            "SELECT thread_id, title, destination, create_at AS created_at, status "
            "FROM conversations WHERE status!='deleted' "
            "ORDER BY create_at DESC LIMIT ?",
            (limit,),
        ) as cur:
            rows = await cur.fetchall() # 一次性取出所有结果
    return [dict(r) for r in rows]


async def get_conversation(thread_id:str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM conversations WHERE thread_id=?",(thread_id,)
        ) as cur:
            row = await cur.fetchone()
        
        if not row:
            return None
        result = dict(row)
        if result.get("trip_plan"):
            result["trip_plan"] = json.loads(result["trip_plan"])
        return result
    
async def delete_conversation(thread_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "UPDATE conversations SET status='deleted' WHERE thread_id=?",
            (thread_id,)
        )
        await db.commit()

        return cur.rowcount > 0