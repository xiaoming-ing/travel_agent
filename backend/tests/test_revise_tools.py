from app.revision.agent import apply_revision
from app.revision.context import get_ctx, reset_ctx
from app.revision.tools import (
    change_day_pace,
    change_transport,
    remove_attraction,
    update_budget_limit,
    update_meal_constraints,
)
from app.schemas import TravelIntent
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
        "app.revision.agent.revise_agent.ainvoke",
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


def make_revision_context() -> dict:
    reset_ctx()
    plan = {
        "destination": "南京",
        "budget": {"attractions": 100, "hotel": 600, "meals": 300, "transport": 200},
        "daily_plans": [
            {
                "day": 1,
                "attraction_names": ["夫子庙", "玄武湖", "总统府"],
                "transport": "公共交通",
                "meals": {"breakfast": "豆浆", "lunch": "本地菜", "dinner": "小吃"},
            }
        ],
        "attractions": [],
    }
    get_ctx().update({
        "plan": plan,
        "raw_attractions": [],
        "raw_hotels": [],
        "transport": "公共交通",
        "intent": TravelIntent(),
    })
    return plan


def test_remove_attraction_and_change_day_pace():
    plan = make_revision_context()

    remove_attraction.invoke({"day": 1, "attraction_name": "总统府"})
    change_day_pace.invoke({"day": 1, "max_attractions": 1})

    assert plan["daily_plans"][0]["attraction_names"] == ["夫子庙"]


def test_change_transport_updates_all_days():
    plan = make_revision_context()

    change_transport.invoke({"new_transport": "打车"})

    assert plan["daily_plans"][0]["transport"] == "打车"


def test_meal_and_budget_tools_update_constraints():
    plan = make_revision_context()

    update_meal_constraints.invoke({"restrictions": ["海鲜"]})
    message = update_budget_limit.invoke({"new_limit": 1000})

    assert "海鲜" in plan["daily_plans"][0]["meals"]["lunch"]
    assert get_ctx()["intent"].dietary_restrictions == ["海鲜"]
    assert get_ctx()["intent"].budget_limit == 1000
    assert "仍然超限" in message
