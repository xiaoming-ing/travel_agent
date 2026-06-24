from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from fastapi import Depends,HTTPException
from app.core.security import decode_access_token
from app.db.conversation_store import get_conversation

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