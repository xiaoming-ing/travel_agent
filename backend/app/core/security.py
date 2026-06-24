import os
import bcrypt
from datetime import datetime,timezone,timedelta
import jwt

JWT_SECRET = os.getenv("JWT_SECRET","dev-secret-change-me")
JWT_ALG = "HS256"
JWT_EXPIRE_HOURS= int(os.getenv("JWT_EXPIRE_HOURS","24"))

def hash_password(plain:str) -> str:
    """明文密码->bcrypt 哈希(自带随机盐),返回可直接入库的字符串。自带随机盐同一个密码，两次哈希的值是不一样的"""
    digest = bcrypt.hashpw(plain.encode("utf-8"),bcrypt.gensalt())
    return digest.decode("utf-8")

def verify_password(plain:str,password_hash:str) -> bool:
    """校验明文是否匹配数据库存的哈希，checkpw会从已存的哈希表里把当初的那撮盐取出来，用同样的盐算一遍再对比"""
    return bcrypt.checkpw(plain.encode("utf-8"),password_hash.encode("utf-8"))

def create_access_token(user_id:str) -> str:
    """签发 JWT:user_id放进sub（载荷，带防伪标签的通行证，是一串用点分成三段的字符串，头部（算法），载荷（user_id,过期时间），签名）
    ,带签发时间和过期时间"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub":user_id,
        "iat":now,
        "exp":now + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload,JWT_SECRET,algorithm=JWT_ALG)

def decode_access_token(token:str) -> str | None:
    """解析JWT：成功返回user_id,过期或者被篡改返回None"""
    try:
        payload = jwt.decode(token,JWT_SECRET,algorithms=[JWT_ALG])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None