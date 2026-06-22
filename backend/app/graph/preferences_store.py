import os
import aiosqlite
import json
from datetime import datetime


DB_PATH = os.getenv("CHECKPOINTS_DB", "checkpoints.db")# 使用环境变量名，不存在用checkpoints.db

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

async def get_preferences(user_id:str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT preferences,accommodation,transport "
            "FROM user_preferences where user_id=?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    try:
        prefs = json.loads(row["preferences"]) if row['preferences'] else []
    except (json.JSONDecodeError,TypeError):
        prefs = []
    return {
        "preferences":prefs,
        "accommodation":row["accommodation"] or "",
        "transport":row["transport"] or ""
    }

async def save_preferences(user_id:str, preferences: list[str],accommodation:str, transport: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO user_preferences (user_id,preferences,accommodation,transport,updated_at) VALUES (?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                preferences=excluded.preferences,
                accommodation=excluded.accommodation,
                transport=excluded.transport,
                updated_at=excluded.updated_at
            """, # ON CONFLICT 如果user_id存在则更新，而不是报错 excluded表示本次准备插入的数据
            (
                user_id,
                json.dumps(preferences,ensure_ascii=False),
                accommodation,
                transport,
                datetime.now().isoformat(),
            )
        )
        await db.commit()

def pref_fields_from_request(request) -> dict:
    """从TripRequest对象或其dict形态(checkpointer回读后可能是个dict取出三个字段)"""
    if isinstance(request,dict):
        prefs = request.get("preferences") or []
        acc = request.get("accommodation") or ""
        trans = request.get("transport") or ""
    else:
        prefs = getattr(request,"preferences",None) or []
        acc = getattr(request, "accommodation", None) or ""
        trans = getattr(request, "transport", None) or ""
    return {"preferences": list(prefs), "accommodation": acc, "transport": trans}
        
async def save_preferences_from_request(user_id:str,request)-> None:
    f = pref_fields_from_request(request)
    await save_preferences(
        user_id, f["preferences"], f["accommodation"], f["transport"]
    )