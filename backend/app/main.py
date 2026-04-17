from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.graph.workflow import graph
from langchain_core.messages import HumanMessage
import json


app = FastAPI(title="旅行智能助手")

# 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

class ChatRequest(BaseModel):
    message:str
    thread_id: str="default"

class ChatResponse(BaseModel):
    reply:str
    destination: str | None = None
    dates: dict | None = None
    budget: float | None = None
    info_complete: bool = False

NODE_LABELS = {
    "supervisor":"理解你的需求",
    "weather":"查询天气",
    "attraction":"查找景点",
    "summarizer":"整理建议"
}


@app.post("/api/chat",response_model=ChatResponse)
async def chat(req: ChatRequest):
    result = graph.invoke(
        {"messages":[HumanMessage(content=req.message)]},
        config={"configurable":{"thread_id":req.thread_id}}
    )

    # 最后1条消息就是surpervisor的回复
    reply = result["messages"][-1].content

    return ChatResponse(
        reply=reply,
        destination=result.get("destination"),
        dates=result.get("dates"),
        budget=result.get("budget"),
        info_complete=bool(
            result.get("destination") and result.get("dates") and result.get("budget")
        )
    )

def sse(event:str,data:dict) -> str:
    """格式化成sse规范"""
    return f"event:{event}\ndata:{json.dumps(data,ensure_ascii=False)}\n\n"

@app.post("/api/chat/stream")
async def chat_stream(req:ChatRequest):
    async def event_generator():
        config = {"configurable":{"thread_id":req.thread_id}}
        inputs = {"messages":[HumanMessage(content=req.message)]}

        supervisor_count = 0

        async for mode,chunk in graph.astream(inputs,config,stream_mode=['updates','messages']):
            if mode == "updates":
                # updates模式下 chunk = {node_name:{state}}
                for node_name,update in chunk.items():
                    if node_name == "supervisor":
                        supervisor_count += 1
                        if supervisor_count == 1:
                            #第一次supervisor运行-把回复文本发给前端
                            msgs = update.get("messages")
                            if msgs:
                                yield sse("messages",{"content":msgs[-1].content})
                            
                            # 判断信息是否齐全，齐全则通知前端即将开始规划
                            state_vals = graph.get_state(config).values
                            dest = state_vals.get("destination")
                            dates = state_vals.get("dates")
                            budget = state_vals.get("budget")
                            # 用具体key判断，避免REST哨兵干扰
                            outputs = state_vals.get("agent_outputs") or {}
                            has_results = "weather" in outputs or "attraction" in outputs
                            if dest and dates and budget and has_results:
                                yield sse("step_start",{"node":"weather","label":"正在查询天气"})
                                yield sse("step_start",{"node":"attraction","label":"正在查找景点"})
                        
                        elif supervisor_count == 2:
                            # 第二次 supervisor（weather/attraction 回来后的路由）→ 即将进 summarizer
                            yield sse("step_start",{"node":"summarizer","label":"正在整理建议"})
                    elif node_name in ("wether","attraction"):
                        # agent完成，带上summary 作为兜底
                        # agent 完成，带上 summary 作为兜底（万一 token 没流出来）
                        outputs = update.get("agent_outputs",{})
                        summary = outputs.get(node_name,"")
                        yield sse("step_done",{"node":node_name,"summary":summary})

                    elif node_name == "summarizer":
                        yield sse("step_done",{"node":"summarizer"})

            elif mode == "messages":
                # LLM token 流 — chunk = (AIMessageChunk, metadata)
                msg_chunk,meta = chunk
                node = meta.get("langgraph_node")
                # 只流 weather/attraction/summarizer 的 token，排除 supervisor（JSON碎片）
                if msg_chunk.content and node in ("weather","attraction","summarizer"):
                    yield sse("token",{"content":msg_chunk.content,"node":node})
        
        # 流结束，推最终 state
        final_state = graph.get_state(config).values
        yield sse("done",{
            "destination": final_state.get("destination"),
            "dates": final_state.get("dates"),
            "budget": final_state.get("budget"),
            "info_complete": bool(
                final_state.get("destination")
                and final_state.get("dates")
                and final_state.get("budget")
            )
        })
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"}
    )
