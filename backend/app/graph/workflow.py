"""
两阶段 Agent 执行器

Phase 1:React Ageent 根据用户需求自主调用工具（search_attractions/get_weather/search_hotels）
    收集规划所需数据。LLM决定调什么、顺序、参数
Phase 2:用Phase 1所收集到的原始数据，调structured output LLM 生成最终TripPlan.
"""

import logging
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain.agents import create_agent
from app.agents.tools import ALL_TOOLS,reset_session, get_session
from app.schemas import TripRequest
from langchain_core.messages import HumanMessage, SystemMessage
from app.agents.itinerary import generate_plan, _fallback_plan
from app.core.tokens import count_tokens
import time
from langchain_core.runnables import RunnableConfig
from langchain_core.callbacks import adispatch_custom_event


load_dotenv()

logger = logging.getLogger(__name__)

# phase 1用的LLM-temperature低，让工具调用决策更稳定
agent_llm = ChatDeepSeek(model="deepseek-chat",temperature=0.2)

AGENT_SYSTEM_PROMPT= """你是一个旅行数据收集助手。用户会提供目的地、日期、交通/住宿偏好。
你的任务是调用工具收集规划行程所需的数据，**不要自己编行程**。

可用工具：
- search_attractions(city, limit): 搜景点
    * preferences 必填！从用户提供的偏好列表里挑对应的传入（例如用户说"美食"，就传 ["美食"]）
    * 取值：历史文化 / 自然风光 / 美食 / 购物 / 艺术 / 休闲 / 亲子
    * 多个偏好一起传会搜到多种类型
- get_weather(city, trip_days): 查天气
- search_hotels(accommodation_type, transport): 搜酒店（必须先查景点）
- search_specific_place(city,keyword): 根据具体地名搜景点

建议流程：
1. 先调 search_attractions 拿景点（规划基础）
2. 若【额外要求】中提到了具体地名（如"想去夫子庙")或可归类的地点类型(如"想去海边"--翻译成"海滨"再搜),调search_specific_place补充
3. 调 get_weather 拿天气
4 调 search_hotels 拿酒店（前提：景点已查到）
5. 数据齐备后直接回复"数据收集完毕"即可

规则：
- 同一工具不要重复调（除非参数不同）
- 总调用次数不超过6次
- 不要在回复里包含行程规划，那是后续步骤工作。

"""

agent = create_agent(agent_llm,tools=ALL_TOOLS)

async def run_workflow(request:TripRequest,config:RunnableConfig | None = None) -> dict:
    """对外入口：输入TripRequest,返回{"trip_plan":dict}"""
    reset_session()

    user_msg = (
        f"目的地：{request.destination}\n"
        f"日期：{request.start_date} 至 {request.end_date}（共 {request.trip_days} 天）\n"
        f"交通方式：{request.transport}\n"
        f"住宿方式：{request.accommodation}\n"
        f"偏好：{','.join(request.preferences) or '无'}\n"
        f"额外要求：{request.extra_requirements or '无'}\n\n"
        f"请调用工具收集规划所需数据。"
    )

    # Phase 1:数据收集
    logger.info("[Phase 1] Agent 开始收集数据...")
    try:
        phase1_result = await agent.ainvoke(
            {
                "messages":[SystemMessage(content=AGENT_SYSTEM_PROMPT),HumanMessage(content=user_msg)]
            },
            config={"recursion_limit":15}
        )
    except Exception as e:
        logger.exception("[Phase 1] 数据收集失败")
        return {"trip_plan":_fallback_plan(request,reason=f"数据收集阶段失败：{e}")}
    
    # Phase 2: 结构化LLM生成行程
    data = get_session()
    if not data["attractions"]:
        return {"trip_plan":_fallback_plan(request, reason="景点数据暂不可用，请稍后重试")}
    
    phase1_tokens = count_tokens(phase1_result.get("messages",[]))
    phase2_started_at = time.perf_counter()
    await adispatch_custom_event(
        "phase2_start",
        {"message":"AI 正在规划行程..."},
        config=config,
    )
    try:
        plan,phase2_tokens = await generate_plan(
            request=request,
            attractions=data["attractions"],
            hotels=data["hotels"],
            weather=data["weather"],
        )
        phase2_elapsed_ms = int((time.perf_counter()- phase2_started_at)*1000)
        await adispatch_custom_event(
              "phase2_end",
              {
                  "message": f"AI 规划完成，用时 {phase2_elapsed_ms / 1000:.1f} 秒",
                  "elapsed_ms": phase2_elapsed_ms,
              },
              config=config,
          )
        return {"trip_plan":plan,"token_used":phase1_tokens + phase2_tokens}
    except Exception as e:
        phase2_elapsed_ms = int((time.perf_counter() - phase2_started_at) * 1000)
        await adispatch_custom_event(
            "phase2_end",
            {
                "message":f"AI 规划失败，用时 {phase2_elapsed_ms / 1000:.1f} 秒",
                "elapsed_ms":phase2_elapsed_ms,
                "failed":True
            },
            config=config
        )
        logger.exception("[Phase 2] 行程生成失败")
        return {"trip_plan": _fallback_plan(request, reason=f"AI 行程生成失败：{e}"), "token_used": phase1_tokens}
