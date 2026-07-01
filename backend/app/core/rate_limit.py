"""
内存态滑动窗口限流器，用于给注册/登录接口防刷。
单进程假设:计数只在这一个 uvicorn worker 里生效——项目本身因 SQLite 已强制 --workers 1，天然满足。
按(bucket, 客户端IP)分别计数，不同用户/不同接口互不影响。
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

# {bucket名: {ip: deque[请求时间戳]}}
_hits: dict[str, dict[str, deque]] = defaultdict(lambda: defaultdict(deque))


def _check_and_record(bucket: str, key: str, limit: int, window_seconds: int) -> None:
    """滑动窗口限流:窗口内超过limit次直接抛429。
    函数内不含 await,asyncio协作式调度下这几行天然原子执行,不用加锁。
    """
    now = time.monotonic()
    hits = _hits[bucket][key]

    # 丢掉窗口外的旧记录
    cutoff = now - window_seconds
    while hits and hits[0] < cutoff:
        hits.popleft()

    if len(hits) >= limit:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    hits.append(now)


def rate_limit(bucket: str, limit: int, window_seconds: int):
    """返回一个 FastAPI 依赖，按客户端 IP + bucket 名限流。
    用法: dependencies=[Depends(rate_limit("register", limit=5, window_seconds=60))]
    """
    async def _dep(request: Request) -> None:
        client_ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")
        _check_and_record(bucket, client_ip, limit, window_seconds)

    return _dep
