"""
user_quota表：按月的token用量配额。
惰性重置--不用定时任务，每月读/写时发现存的period不是本月，就先清零再继续。
"""

import os
import aiosqlite
from datetime import datetime

DB_PATH = os.getenv("CHECKPOINTS_DB","checkpoints.db")
DEFAULT_TOKEN_QUOTA = int(os.getenv("DEFAULT_TOKEN_QUOTA",'200000'))

def _current_period() -> str:
    """当前所属周期，格式'YYYY-MM'"""
    return datetime.now().strftime("%Y-%m")

async def init_quota_table() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_quota (
                user_id TEXT PRIMARY KEY,
                token_limit INTEGER NOT NULL,
                token_used INTEGER NOT NULL DEFAULT 0,
                period TEXT NOT NULL,
                updated_at TEXT
            )"""
        )
        await db.commit()

async def _ensure_current_period(db:aiosqlite.Connection,user_id:str) -> tuple[int,int]:
    """确保这一行存在且属于本月；返回（token_limit,token_used)。跨月自动清零。"""
    period = _current_period()
    async with db.execute(
        "SELECT token_limit,token_used,period FROM user_quota WHERE user_id=?", (user_id,)
    ) as cur:
        row = await cur.fetchone()

    if row is None:
        await db.execute(
            "INSERT INTO user_quota (user_id,token_limit,token_used,period,updated_at) "
            "VALUES (?,?,0,?,?)",
            (user_id,DEFAULT_TOKEN_QUOTA,period,datetime.now().isoformat()),
        )
        await db.commit()
        return DEFAULT_TOKEN_QUOTA, 0
    
    token_limit,token_used,row_period = row
    if row_period != period:
        await db.execute(
            "UPDATE user_quota SET token_used=0,period=?,updated_at=? where user_id=?",
            (period,datetime.now().isoformat(),user_id),
        )
        await db.commit()
        return token_limit, 0
    
    return token_limit, token_used

async def get_remaining(user_id:str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        limit,used = await _ensure_current_period(db,user_id)
    return max(limit - used,0)

async def has_quota(user_id:str) -> bool:
    return await get_remaining(user_id) > 0

async def add_usage(user_id:str,tokens:int) -> None:
    """本轮实际消耗的tokens累加进used。tokens<=0时不做任何事。"""
    if tokens <= 0:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_current_period(db,user_id)
        await db.execute(
            "UPDATE user_quota SET token_used = token_used + ?,updated_at=? where user_id=?",
            (tokens,datetime.now().isoformat(),user_id)
        )
        await db.commit()