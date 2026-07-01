"""
SSE streaming 工具：把LangGraph 的astream_events事件流转成用户可读的进度消息。

LanGraph的astream_events会穿透到嵌套的子图/ReAct Agent内部的每一次工具调用、LLM调用。我们只对关心的工具事件发消息，其他全部过滤掉
"""
import json
from typing import Any,AsyncIterator,Callable,Awaitable

def format_sse(event_data:dict) -> str:
    """SSE报文格式：data:<json>\\n\\n"""
    return f"data:{json.dumps(event_data,ensure_ascii=False)}\n\n"

# 工具名 -> (开始提示，完成提示)
TOOL_MESSAGES:dict[str,tuple[str,str]] = {
    "search_attractions":       ("🔧 正在搜索景点...",       "✅ 景点候选已就绪"),
    "get_weather":              ("🔧 正在查询天气...",       "✅ 天气数据已获取"),
    "search_hotels":            ("🔧 正在搜索酒店...",       "✅ 酒店 Top 5 已打分"),
    "replace_day_attractions":  ("🔧 正在替换景点...",       "✅ 当天景点已更新"),
    "change_hotel_type":        ("🔧 正在重新搜索酒店...",   "✅ 酒店候选已更新"),
    "search_attraction_by_name":("",                          ""),   # 静默，太细不推
}

def extract_interrupt(state) -> dict | None:
    if not state.tasks:
        return None
    for task in state.tasks:
        if task.interrupts:
            return task.interrupts[0].value
    return None

async def stream_graph(
    graph:Any,
    input_data:Any,
    config:dict,
    on_done: Callable[[dict],Awaitable[None]] | None = None,
    on_tokens: Callable[[int],Awaitable[None]] | None = None,
) -> AsyncIterator[str]:
    """跑图、yield SSE 字符串。末尾yield最终need_input 或done事件。"""
    # 开场
    yield format_sse({"type":"progress","message":"🚀 开始处理请求..."})
    turn_tokens = 0 # 这一轮（本次start/resume调用）真实消耗的token总数
    # 跑图并监听事件
    try:
        async for event in graph.astream_events(input_data,config=config,version="v2"):
            kind = event.get("event")
            name = event.get("name","")

            if kind == "on_tool_start" and name in TOOL_MESSAGES:
                start_msg,_ = TOOL_MESSAGES[name]
                if start_msg:
                    yield format_sse({"type":"progress","message":start_msg})
            
            elif kind == "on_tool_end" and name in TOOL_MESSAGES:
                _,end_msg = TOOL_MESSAGES[name]
                if end_msg:
                    yield format_sse({"type":"progress","message":end_msg})
            
            # Phase 2 合成行程中（识别进入plan/revise节点）
            elif kind == 'on_chain_start' and name == 'plan':
                yield format_sse({"type":"progress","message":"🧠 Phase 2：AI 合成行程中..."})
            elif kind == 'on_chain_end' and name == 'revise':
                yield format_sse({"type":"progress","message":"🧠 正在应用修改..."})

            # 捕获plan/revise节点跑完时返回token_used,累加到这一轮的总消耗里面
            if kind == "on_chain_end" and name in ('plan','revise'):
                output = event.get('data',{}).get('output') or {}
                turn_tokens += output.get('token_used',0) or 0

    except Exception as e:
        yield format_sse({"type":"error","message":f"执行失败：{e}"})
        return
    
    # 不管这轮是“暂停等反馈”还是“图跑完了”，只要消耗了token就记账
    if on_tokens and turn_tokens:
        await on_tokens(turn_tokens)

    # 结束状态检查
    state = await graph.aget_state(config)
    interrupt_payload = extract_interrupt(state)
    thread_id = config["configurable"]["thread_id"]

    if interrupt_payload: # state.tasks里面有挂起的interrupt
        yield format_sse({
            "type": "need_input",
            "thread_id": thread_id,
            "interrupt_type": interrupt_payload.get("type"),
            "question": interrupt_payload.get("question"),
            "trip_plan": interrupt_payload.get("trip_plan"),
        })
    else: # 图跑完
        trip_plan = state.values.get("trip_plan")
        if on_done and trip_plan:
            await on_done(trip_plan)
        yield format_sse({
            "type":"done",
            "thread_id":thread_id,
            "trip_plan":state.values.get("trip_plan")
        })