from app.agents.revise_tools import apply_revision
import pytest
from unittest.mock import AsyncMock,patch

@pytest.mark.asyncio
async def test_apply_revision():
    """测试apply_revision函数基本功能。"""
    original_plan = {
        "destination": "南京",
        "trip_days": 1,
        "daily_plans": [
            {
                "day": 1,
                "date": "2026-07-01",
                "attraction_names": ["夫子庙"],
            }
        ],
        "attractions": [],
        "hotels": [],
    }

    failing_invoke = AsyncMock(side_effect=RuntimeError("LLM timeout"))

    with patch(
        "app.agents.revise_tools.revise_agent.ainvoke",
        new=failing_invoke
    ):
        plan,tokens,note = await apply_revision(
            feedback="太累了，换成室内活动",
            current_plan=original_plan,
            raw_attractions=[],
            raw_hotels=[],
            transport="公共交通",
        )
    assert plan == original_plan
    assert tokens == 0
    assert note == "修改服务暂时不可用，请稍后重试"