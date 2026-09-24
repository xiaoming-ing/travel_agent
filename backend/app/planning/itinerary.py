"""Phase 2：根据已收集的数据生成并校验最终行程。"""

import json
import logging

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_deepseek import ChatDeepSeek

from app.core.tokens import count_tokens
from app.planning.postprocess import _postprocess_plan
from app.planning.prompts import _build_itinerary_prompt
from app.planning.validator import validate_plan
from app.rag.retriever import retrieve_for_attractions
from app.schemas import Attraction, Hotel, TravelIntent, TripPlan, TripRequest

load_dotenv()

logger = logging.getLogger(__name__)
llm = ChatDeepSeek(model="deepseek-chat", temperature=0.5)


async def generate_plan(
    request: TripRequest,
    attractions: list[Attraction],
    hotels: list[Hotel],
    weather: list[dict],
    intent: TravelIntent,
    user_id: str = "",
) -> tuple[dict, int]:
    """用 Phase 1 收集到的数据生成完整 TripPlan。"""
    hotel_price_range = hotels[0].price_range if hotels else "300-500元"
    knowledge = await retrieve_for_attractions(
        user_id=user_id,
        city=request.destination,
        names=[attraction.name for attraction in attractions],
    )
    if knowledge:
        logger.info("[RAG]%d个景点命中用户资料", len(knowledge))

    prompt = _build_itinerary_prompt(
        request=request,
        intent=intent,
        attractions=attractions,
        weather=weather,
        hotel_price_range=hotel_price_range,
        knowledge=knowledge,
    )

    try:
        planner = llm.with_structured_output(TripPlan, include_raw=True)
        logger.info("[Phase2] 生成行程中...")
        response = await planner.ainvoke([SystemMessage(content=prompt)])
        result: TripPlan | None = response.get("parsed")
        if result is None:
            parsing_error = response.get("parsing_error")
            reason = (
                f"schema 解析异常：{parsing_error}"
                if parsing_error
                else "模型未返回结构化输出（tool_calls 为空）"
            )
            raise ValueError(reason)
    except Exception as error:
        logger.exception("[Phase2] LLM 调用失败")
        return _fallback_plan(request, reason=f"AI 行程生成失败：{error}"), 0

    logger.debug("Phase2 原始输出: %s", response)
    tokens = count_tokens([response["raw"]]) if response.get("raw") is not None else 0
    plan = _postprocess_plan(
        result=result,
        raw_attractions=attractions,
        hotels=hotels,
        weather=weather,
        destination=request.destination,
    )
    validation = validate_plan(plan, intent)

    if not validation.passed:
        repair_request = (
            "上一次生成的行程未通过确定性校验。请根据违规项返回一份完整修正版行程。\n"
            f"违规项：{json.dumps(validation.violations, ensure_ascii=False)}\n"
            f"待修正行程：{json.dumps(plan, ensure_ascii=False)}\n"
            "只修正规则冲突，不要忽略原始硬约束，也不要引入候选列表外的景点。"
        )
        try:
            repair_response = await planner.ainvoke(
                [
                    SystemMessage(content=prompt),
                    HumanMessage(content=repair_request),
                ]
            )
            repaired_result: TripPlan | None = repair_response.get("parsed")
            if repaired_result is not None:
                plan = _postprocess_plan(
                    result=repaired_result,
                    raw_attractions=attractions,
                    hotels=hotels,
                    weather=weather,
                    destination=request.destination,
                )
                validation = validate_plan(plan, intent)
                if repair_response.get("raw") is not None:
                    tokens += count_tokens([repair_response["raw"]])
        except Exception:
            logger.exception("[Phase2] 定向修正失败，保留可用行程")

    if not validation.passed:
        warning = "；".join(validation.violations)
        plan["suggestion"] = (
            f"{plan.get('suggestion', '')}\n⚠️ 以下要求暂未完全满足：{warning}"
        ).strip()
    return plan, tokens


def _fallback_plan(request: TripRequest, reason: str) -> dict:
    """Phase 1 或 Phase 2 失败时返回最小可用计划。"""
    return {
        "destination": request.destination,
        "start_date": str(request.start_date),
        "end_date": str(request.end_date),
        "trip_days": request.trip_days,
        "suggestion": f"⚠️ {reason}",
        "budget": {"attractions": 0, "hotel": 0, "meals": 0, "transport": 0},
        "attractions": [],
        "daily_plans": [],
        "hotels": [],
        "weather_summary": "",
    }
