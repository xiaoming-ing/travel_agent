"""run_workflow 的兜底逻辑：Phase1/Phase2 出错时应返回 _fallback_plan，而不是抛异常。"""
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from app.schemas import TripRequest
from app.graph.workflow import run_workflow


def make_request() -> TripRequest:
    return TripRequest(
        destination="南京",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 3),
        preferences=["历史文化"],
    )


@pytest.mark.asyncio
async def test_phase1_failure_returns_fallback_plan():
    with patch("app.graph.workflow.agent.ainvoke", new=AsyncMock(side_effect=RuntimeError("LLM 超时"))):
        result = await run_workflow(make_request())

    plan = result["trip_plan"]
    assert plan["attractions"] == []
    assert plan["daily_plans"] == []
    assert "数据收集阶段失败" in plan["suggestion"]


@pytest.mark.asyncio
async def test_no_attractions_returns_fallback_plan():
    with patch("app.graph.workflow.agent.ainvoke", new=AsyncMock(return_value=None)), \
         patch("app.graph.workflow.get_session", return_value={"attractions": [], "hotels": [], "weather": []}):
        result = await run_workflow(make_request())

    plan = result["trip_plan"]
    assert plan["attractions"] == []
    assert "景点数据暂不可用" in plan["suggestion"]
