
from pydantic import Field,BaseModel
from fastapi import APIRouter, HTTPException,Depends
from app.db.user_store import create_user,get_user_by_name
from app.core.security import hash_password,create_access_token,verify_password
from app.core.rate_limit import rate_limit

router = APIRouter()

class RegisterBody(BaseModel):
    username: str = Field(min_length=1,max_length=32)
    password: str = Field(min_length=6,max_length=128)

class LoginBody(BaseModel):
    username:str
    password:str

@router.post(
    "/api/auth/register",
    dependencies=[Depends(rate_limit("register", limit=5, window_seconds=60))],
)
async def register(body:RegisterBody):
    user_id = await create_user(body.username, hash_password(body.password))
    if user_id is None:
        raise HTTPException(status_code=409,detail="用户名已被占用")
    # 注册成功顺手登录：直接签一张token发回，前端不用再一次登录
    token = create_access_token(user_id)
    return {"token":token,"user_id":user_id,"username":body.username}

@router.post(
        "/api/auth/login",
        dependencies=[Depends(rate_limit("login", limit=10, window_seconds=60))],
)
async def login(body: LoginBody):
    user = await get_user_by_name(body.username)
    if not user or not verify_password(body.password,user["password_hash"]):
        raise HTTPException(status_code=401,detail="用户名或密码错误")
    token = create_access_token(user["user_id"])
    return {"token":token,"user_id":user["user_id"],"username":body.username}