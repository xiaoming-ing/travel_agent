from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from fastapi import Depends,HTTPException
from app.core.security import decode_access_token
from app.db.conversation_store import get_conversation
from app.db.user_store import get_user_role
from app.db.quota_store import has_quota

bearer_scheme = HTTPBearer() # 告诉FastAPI: 从Authorization: Bearer 头取token

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    """解析token -> 返回 user_id;过期/被篡改/无效 -> 401."""
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status_code=401,detail="登录已失效，请重新登录")
    return user_id

async def get_owned_conversation(thread_id:str,user_id:str) -> dict:
    """取出对话并确认归属；不存在或不属于你，都回404"""
    conv = await get_conversation(thread_id)
    if not conv or conv.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conv

async def require_quota(user_id:str=Depends(get_current_user_id)) -> str:
    """在已登录的基础上多一层配额校验：admin直接放行，普通用户配额用尽则429."""
    role = await get_user_role(user_id)
    if role == "admin":
        return user_id
    if not await has_quota(user_id):
        raise HTTPException(status_code=429, detail="配额已用尽")
    return user_id