"""长期记忆:按 user_id 读取偏好画像,供前端表单预选。"""
from fastapi import APIRouter,Depends

from app.db.preferences_store import get_preferences
from app.api.deps import get_current_user_id

router = APIRouter()


@router.get("/api/preferences")
async def get_user_preferences(user_id: str = Depends(get_current_user_id)):
    """user_id 来自token,前端无法伪造去读别人的偏好。"""
    prefs = await get_preferences(user_id)
    return prefs or {}
