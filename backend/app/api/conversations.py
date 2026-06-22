"""历史对话相关路由:列表 / 详情 / 删除 / 实时状态 / 标记完成。"""
from fastapi import APIRouter, Request, HTTPException

from app.graph.streaming import extract_interrupt
from app.db.conversation_store import (
    list_conversations, get_conversation, delete_conversation, complete_conversation,
)

router = APIRouter()


@router.get("/api/conversations")
async def get_conversations():
    return await list_conversations()


@router.get("/api/conversations/{thread_id}")
async def get_one_conversation(thread_id: str):
    conv = await get_conversation(thread_id)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conv


@router.delete("/api/conversations/{thread_id}")
async def delete_one_conversation(thread_id: str):
    success = await delete_conversation(thread_id)
    if not success:
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"ok": True, "messages": "删除成功"}


@router.get("/api/conversations/{thread_id}/state")
async def get_conv_state(thread_id: str, request: Request):
    """查对话的实时状态：有 interrupt → 进行中，有 trip_plan → 已完成"""
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = await request.app.state.conv_graph.aget_state(config)
    except Exception:
        raise HTTPException(status_code=404, detail="对话不存在")

    interrupt_payload = extract_interrupt(state)
    if interrupt_payload:
        return {
            "status": "need_input",
            "question": interrupt_payload.get("question"),
            "trip_plan": interrupt_payload.get("trip_plan"),
        }

    trip_plan = state.values.get("trip_plan")
    if trip_plan:
        return {"status": "done", "trip_plan": trip_plan}

    return {"status": "unknown"}


@router.post("/api/conversations/{thread_id}/complete")
async def mark_conversation_complete(thread_id: str, request: Request):
    """用户直接点'查看完整行程'时调用，把对话标记为 done。"""
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = await request.app.state.conv_graph.aget_state(config)
        trip_plan = state.values.get("trip_plan")
        if trip_plan:
            await complete_conversation(thread_id, trip_plan)
            return {"ok": True}
        return {"ok": False, "reason": "no trip_plan"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
