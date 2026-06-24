"""会话相关路由:开新会话 / 续跑(均为 SSE 流式)。"""
import logging
import uuid

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel

from app.schemas import TripRequest
from app.graph.streaming import stream_graph
from app.db.conversation_store import (
    create_conversation, complete_conversation, get_conversation,
)
from app.db.preferences_store import save_preferences_from_request
from app.api.deps import get_current_user_id, get_owned_conversation

logger = logging.getLogger(__name__)

router = APIRouter()

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",   # 禁用可能的反代缓冲
}


class ChatStartBody(BaseModel):
    request: TripRequest

class ChatResumeBody(BaseModel):
    thread_id: str
    answer: str


async def _persist_preferences(graph, config, thread_id: str) -> None:
    """行程完成时把最终 request 的 3 个偏好字段写回长期记忆。失败不影响主流程。"""
    try:
        conv = await get_conversation(thread_id)
        user_id = (conv or {}).get("user_id") or ""
        if not user_id:
            return
        state = await graph.aget_state(config)
        req = state.values.get("request")
        if req is None:
            return
        await save_preferences_from_request(user_id, req)
    except Exception:
        logger.warning("保存用户偏好失败", exc_info=True)


@router.post("/api/chat/start-stream")
async def chat_start_stream(
    body: ChatStartBody, 
    request: Request,
    user_id: str = Depends(get_current_user_id)
    ):
    """流式版开会话。客户端按SSE协议读事件。"""
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    graph = request.app.state.conv_graph

    await create_conversation(
        thread_id,
        body.request.destination,
        str(body.request.start_date),
        str(body.request.end_date),
        user_id,
    )

    async def on_done(trip_plan: dict):
        await complete_conversation(thread_id, trip_plan)
        await _persist_preferences(graph, config, thread_id)

    return StreamingResponse(
        stream_graph(graph, {"request": body.request}, config, on_done=on_done),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/api/chat/resume-stream")
async def chat_resume_stream(
    body: ChatResumeBody, 
    request: Request,
    user_id: str = Depends(get_current_user_id),
    ):
    """流式版续跑。"""
    await get_owned_conversation(body.thread_id, user_id)
    config = {"configurable": {"thread_id": body.thread_id}}
    graph = request.app.state.conv_graph

    async def on_done(trip_plan: dict):
        await complete_conversation(body.thread_id, trip_plan)
        await _persist_preferences(graph, config, body.thread_id)

    return StreamingResponse(
        stream_graph(graph, Command(resume=body.answer), config, on_done=on_done),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
