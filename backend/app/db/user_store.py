import os
import aiosqlite
import uuid
from datetime import datetime

DB_PATH = os.getenv("CHECKPOINTS_DB","checkpoints.db")

async def init_user_table() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT,
                role TEXT NOT NULL DEFAULT 'user'
            )
            """
        )
        await db.commit()

async def create_user(username:str,password_hash:str) -> str | None:
    """新建用户，返回新生成的user_id;用户名存在则返回None"""
    user_id = str(uuid.uuid4())
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO users (user_id,username, password_hash,created_at) "
                "VALUES (?,?,?,?)",
                (user_id,username,password_hash,datetime.now().isoformat())
            )
            await db.commit()
        return user_id
    except aiosqlite.IntegrityError:
        return None

async def get_user_by_name(username:str) -> dict | None:
    """登录时用：按用户名查出user_id和password_hash 以便校验密码。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id,password_hash FROM users WHERE username=?",
            (username,),
        ) as cur:
            row = await cur.fetchone()
    return dict(row) if row else None