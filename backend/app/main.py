from dotenv import load_dotenv
load_dotenv()  # 必须在任何 app.* import 之前，否则 weather.py 等模块顶部 os.getenv 拿不到 .env 里的值

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
import traceback

from app.graph.workflow import run_workflow
from app.schemas import TripPlan,TripRequest

from contextlib import asynccontextmanager
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.graph.conversation import build_conversation_builder
from pydantic import BaseModel
import uuid
from langgraph.types import Command
from fastapi.responses import StreamingResponse
from app.graph.streaming import stream_graph
from app.graph.conversation_store import (
    init_table, create_conversation, complete_conversation,
    list_conversations, get_conversation,delete_conversation
)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",   # 禁用可能的反代缓冲
}

# 应用生命周期：启动时打开 SQLite链接 + 编译 conversation graph;结束时闭关
@asynccontextmanager
async def lifespan(app:FastAPI):
    await init_table() 
    async with AsyncSqliteSaver.from_conn_string("checkpoints.db") as checkpointer: # 创建一个LangGraph的持久化存储，让我的对话可恢复
        app.state.conv_graph = build_conversation_builder().compile(checkpointer=checkpointer)
        print("[lifespan] conversation graph 已就绪，checkpoints.db 已连接")
        yield
    print("[lifespan] checkpoints.db 已关闭")

app = FastAPI(title="旅行智能助手",lifespan=lifespan)

# 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.post("/api/plan",response_model=TripPlan)
async def plan(req:TripRequest):
    """
    生成完整旅行计划

    - 入参 TripRequest:FastAPI 自动按schema校验，缺必填字段会返回422
    - 出参 Tripplan:response_model指定后，FastAPI会过滤多余字段、按schema序列化
    """

    try:
        # ainvoke:异步跑完整个图，返回最终state
        # （如果以后想要“正在查天气。。。”这种流式进度，可以换成astream)
        final_state = await run_workflow(req)
    except Exception as e:
        # LanGraph里任何节点抛异常都会冒到这
        traceback.print_exc()
        raise HTTPException(status_code=500,detail=f"生成行程失败：{e}")
    
    trip_plan = final_state.get("trip_plan")
    if not trip_plan:
        raise HTTPException(status_code=500,detail="行程生成结果为空")
    
    return trip_plan

class ChatStartBody(BaseModel):
    request:TripRequest
class ChatResumeBody(BaseModel):
    thread_id:str
    answer:str

def _extract_interrupt(state) -> dict | None:
    """如果图停在interrupt,返回interrupt payload,否则返回None"""
    if not state.tasks:
        return None
    for task in state.tasks:
        if task.interrupts:
            return task.interrupts[0].value
    return None

@app.post("/api/chat/start")
async def chat_start(body:ChatStartBody):
    """开新会话。返回要么need_input（附带Agent的提问），要么done(附带行程)。"""
    thread_id = str(uuid.uuid4)
    config = {"configurable":{"thread_id":thread_id}}
    graph = app.state.conv_graph

    try:
        result = await graph.ainvoke({"request":body.request},config=config)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500,detail=f"会话启动失败：{e}")
    
    state = await graph.aget_state(config)
    interrupt_payload = _extract_interrupt(state)
    if interrupt_payload:
        return {
            "thread_id":thread_id,
            "status":"need_input",
            "interrupt_type":interrupt_payload.get("type"),
            "question":interrupt_payload.get("question"),
            "trip_plan":interrupt_payload.get("trip_plan")
        }

    return {
        "thread_id": thread_id,
        "status": "done",
        "trip_plan": result.get("trip_plan"),
    }

@app.post("/api/chat/resume")
async def chat_resume(body:ChatResumeBody):
    """续跑已暂停的会话，用用户的答复恢复图执行"""
    config = {"configurable":{"thread_id":body.thread_id}}
    graph  = app.state.conv_graph

    try:
        result = await graph.ainvoke(Command(resume=body.answer),config=config)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500,detail=f"会话续跑失败：{e}")
    
    state = await graph.aget_state(config)
    interrupt_payload = _extract_interrupt(state)
    if interrupt_payload:
        return {
            "thread_id": body.thread_id,
            "status": "need_input",
            "interrupt_type": interrupt_payload.get("type"),
            "question": interrupt_payload.get("question"),
            "trip_plan":interrupt_payload.get("trip_plan")
        }
    return {
        "thread_id": body.thread_id,
        "status": "done",
        "trip_plan": result.get("trip_plan"),
    }

@app.post("/api/chat/start-stream")
async def chat_start_stream(body:ChatStartBody):
    """流式版开会话。客户端按SSE协议读事件。"""
    thread_id = str(uuid.uuid4())
    config = {"configurable":{"thread_id":thread_id}}
    graph = app.state.conv_graph

    await create_conversation( # 建记录
        thread_id,
        body.request.destination,
        str(body.request.start_date),
        str(body.request.end_date)
    )

    async def on_done(trip_plan:dict):
        await complete_conversation(thread_id,trip_plan)
    
    return StreamingResponse(
        stream_graph(graph,{"request":body.request},config,on_done=on_done),
        media_type="text/event-stream",
        headers=SSE_HEADERS
    )

@app.post("/api/chat/resume-stream")
async def chat_resume_stream(body: ChatResumeBody):
    """流式版续跑。"""
    config = {"configurable": {"thread_id": body.thread_id}}
    graph = app.state.conv_graph

    async def on_done(trip_plan: dict):
        await complete_conversation(body.thread_id, trip_plan)

    return StreamingResponse(
        stream_graph(graph, Command(resume=body.answer), config, on_done=on_done),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )

# 列出历史对话
@app.get("/api/conversations")
async def get_conversations():
    return await list_conversations()

# 查单个对话
@app.get("/api/conversations/{thread_id}")
async def get_one_conversation(thread_id:str):
    conv = await get_conversation(thread_id)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conv

# 删除
@app.delete("/api/conversations/{thread_id}")
async def delete_one_conversation(thread_id: str):
    success = await delete_conversation(thread_id)

    if not success:
        raise HTTPException(status_code=404, detail="对话不存在")
    
    return {"ok":True,"messages":"删除成功"}



@app.get("/api/conversations/{thread_id}/state")
async def get_conv_state(thread_id: str):
    """查对话的实时状态：有 interrupt → 进行中，有 trip_plan → 已完成"""
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = await app.state.conv_graph.aget_state(config)
    except Exception:
        raise HTTPException(status_code=404, detail="对话不存在")

    # 有 interrupt = 等用户输入
    for task in (state.tasks or []):
        if task.interrupts:
            return {
                "status": "need_input",
                "question": task.interrupts[0].value.get("question"),
                "trip_plan": task.interrupts[0].value.get("trip_plan"),
            }

    # 有 trip_plan = 完成了
    trip_plan = state.values.get("trip_plan")
    if trip_plan:
        return {"status": "done", "trip_plan": trip_plan}

    return {"status": "unknown"}

@app.post("/api/conversations/{thread_id}/complete")
async def mark_conversation_complete(thread_id: str):
    """用户直接点'查看完整行程'时调用，把对话标记为 done。"""
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = await app.state.conv_graph.aget_state(config)
        trip_plan = state.values.get("trip_plan")
        if trip_plan:
            await complete_conversation(thread_id, trip_plan)
            return {"ok": True}
        return {"ok": False, "reason": "no trip_plan"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def heath():
    return {"status":"ok"}