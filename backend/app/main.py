from dotenv import load_dotenv
load_dotenv()  # 必须在任何 app.* import 之前，否则 weather.py 等模块顶部 os.getenv 拿不到 .env 里的值

import logging
import os

# 日志级别由环境变量控制：生产设 INFO/WARNING，开发设 DEBUG
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException

from app.schemas import TripRequest

from contextlib import asynccontextmanager
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.graph.conversation import build_conversation_builder
from pydantic import BaseModel
import uuid
from langgraph.types import Command
from fastapi.responses import StreamingResponse
from app.graph.streaming import stream_graph, extract_interrupt
from app.db.conversation_store import (
    init_table, create_conversation, complete_conversation,
    list_conversations, get_conversation,delete_conversation
)
from app.db.preferences_store import (
    init_pref_table, get_preferences, save_preferences_from_request
)
from app.api import chat, conversations

DB_PATH = os.getenv("CHECKPOINTS_DB","checkpoints.db")

# 应用生命周期：启动时打开 SQLite链接 + 编译 conversation graph;结束时闭关
@asynccontextmanager
async def lifespan(app:FastAPI):
    await init_table()
    await init_pref_table()
    async with AsyncSqliteSaver.from_conn_string(DB_PATH) as checkpointer: # 创建一个LangGraph的持久化存储，让我的对话可恢复
        app.state.conv_graph = build_conversation_builder().compile(checkpointer=checkpointer)
        logger.info("conversation graph 已就绪，checkpoints.db 已连接")
        yield
    logger.info("checkpoints.db 已关闭")

app = FastAPI(title="旅行智能助手",lifespan=lifespan)

_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

# 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(chat.router)
app.include_router(conversations.router)

@app.get("/api/preferences/{user_id}")
async def get_user_preferences(user_id: str):
    """前端表单挂载时拉取:命中返回 3 字段,未命中返回 {} 让前端回退默认值。"""
    prefs = await get_preferences(user_id)
    return prefs or {}

@app.get("/api/health")
async def heath():
    return {"status":"ok"}