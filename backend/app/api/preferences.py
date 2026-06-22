"""长期记忆:按 user_id 读取偏好画像,供前端表单预选。"""
from fastapi import APIRouter

from app.db.preferences_store import get_preferences

router = APIRouter()


@router.get("/api/preferences/{user_id}")
async def get_user_preferences(user_id: str):
    """前端表单挂载时拉取:命中返回 3 字段,未命中返回 {} 让前端回退默认值。"""
    prefs = await get_preferences(user_id)
    return prefs or {}
