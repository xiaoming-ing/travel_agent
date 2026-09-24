"""run_workflow 的兜底逻辑：Phase1/Phase2 出错时应返回 _fallback_plan，而不是抛异常。"""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.graph.workflow import build_search_preferences, run_workflow
from app.schemas import Attraction, TravelIntent, TripRequest


def make_request() -> TripRequest:
    return TripRequest(
        destination="南京",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 3),
        preferences=["历史文化"],
    )


def make_fake_search_tool() -> MagicMock:
    fake_tool = MagicMock()
    fake_tool.ainvoke = AsyncMock(return_value="查询成功")
    return fake_tool


def make_attraction(name: str) -> Attraction:
    return Attraction(
        name=name,
        address=f"{name}地址",
        longitude=118.0,
        latitude=32.0,
        description=f"{name}简介",
    )


def test_build_search_preferences_merges_themes_and_travelers():
    result = build_search_preferences(
        ["历史文化"],
        TravelIntent(
            themes=["夜景", "艺术展"],
            traveler_types=["child"],
        ),
    )

    assert result == ["历史文化", "休闲", "艺术", "亲子"]


@pytest.mark.asyncio
async def test_phase1_failure_returns_fallback_plan():
    with patch(
        "app.graph.workflow.agent.ainvoke",
        new=AsyncMock(side_effect=RuntimeError("LLM 超时")),
    ):
        result = await run_workflow(
            request=make_request(),
            intent=TravelIntent(),
        )

    plan = result["trip_plan"]
    assert plan["attractions"] == []
    assert plan["daily_plans"] == []
    assert "数据收集阶段失败" in plan["suggestion"]


@pytest.mark.asyncio
async def test_no_attractions_returns_fallback_plan():
    with patch(
        "app.graph.workflow.agent.ainvoke",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.graph.workflow.get_session",
        return_value={"attractions": [], "hotels": [], "weather": []},
    ):
        result = await run_workflow(
            request=make_request(),
            intent=TravelIntent(),
        )

    plan = result["trip_plan"]
    assert plan["attractions"] == []
    assert "景点数据暂不可用" in plan["suggestion"]

@pytest.mark.asyncio
async def test_phase1_message_contains_structured_intent():
    intent = TravelIntent(
        must_visit=["夫子庙"],
        avoid_places=["总统府"],
        themes=["古建筑"],
        pace="relaxed",
    )

    fake_agent_result = {"messages": []}
    fake_search_tool = make_fake_search_tool()

    with patch(
        "app.graph.workflow.agent.ainvoke",
        new=AsyncMock(return_value=fake_agent_result),
    ) as mock_ainvoke, patch(
        "app.graph.workflow.search_specific_place",
        new=fake_search_tool,
    ), patch(
        "app.graph.workflow.get_session",
        return_value={
            "attractions": [],
            "hotels": [],
            "weather": [],
        },
    ):
        await run_workflow(
            request=make_request(),
            intent=intent,
        )

    invocation = mock_ainvoke.await_args.args[0]
    messages = invocation["messages"]
    human_message = messages[1].content

    assert "【结构化旅行意图】" in human_message
    assert "夫子庙" in human_message
    assert "总统府" in human_message
    assert "古建筑" in human_message
    assert '"pace": "relaxed"' in human_message

    fake_search_tool.ainvoke.assert_awaited_once_with({
        "city": "南京",
        "keyword": "夫子庙",
    })

@pytest.mark.asyncio
async def test_all_must_visit_places_are_queried():
    intent = TravelIntent(
        must_visit=["夫子庙", "中山陵"],
    )

    fake_agent_result = {"messages": []}
    fake_search_tool = make_fake_search_tool()

    with patch(
        "app.graph.workflow.agent.ainvoke",
        new=AsyncMock(return_value=fake_agent_result),
    ), patch(
        "app.graph.workflow.search_specific_place",
        new=fake_search_tool,
    ), patch(
        "app.graph.workflow.get_session",
        return_value={
            "attractions": [],
            "hotels": [],
            "weather": [],
        },
    ):
        await run_workflow(
            request=make_request(),
            intent=intent,
        )

    assert fake_search_tool.ainvoke.await_count == 2

    fake_search_tool.ainvoke.assert_has_awaits(
        [
            call({
                "city": "南京",
                "keyword": "夫子庙",
            }),
            call({
                "city": "南京",
                "keyword": "中山陵",
            }),
        ]
    )


@pytest.mark.asyncio
async def test_avoided_attractions_are_filtered_before_generate_plan():
    candidates = [
        make_attraction("夫子庙"),
        make_attraction("总统府"),
        make_attraction("玄武湖"),
    ]
    session = {
        "attractions": candidates,
        "hotels": [],
        "weather": [],
    }
    fake_generate_plan = AsyncMock(return_value=({"attractions": []}, 0))

    with patch(
        "app.graph.workflow.agent.ainvoke",
        new=AsyncMock(return_value={"messages": []}),
    ), patch(
        "app.graph.workflow.get_session",
        return_value=session,
    ), patch(
        "app.graph.workflow.generate_plan",
        new=fake_generate_plan,
    ), patch(
        "app.graph.workflow.adispatch_custom_event",
        new=AsyncMock(),
    ):
        await run_workflow(
            request=make_request(),
            intent=TravelIntent(avoid_places=["总统府"]),
        )

    passed_attractions = fake_generate_plan.await_args.kwargs["attractions"]
    assert [item.name for item in passed_attractions] == ["夫子庙", "玄武湖"]


@pytest.mark.asyncio
async def test_filtering_preserves_candidate_order():
    candidates = [
        make_attraction("玄武湖"),
        make_attraction("总统府"),
        make_attraction("夫子庙"),
    ]
    session = {
        "attractions": candidates,
        "hotels": [],
        "weather": [],
    }
    fake_generate_plan = AsyncMock(return_value=({"attractions": []}, 0))

    with patch(
        "app.graph.workflow.agent.ainvoke",
        new=AsyncMock(return_value={"messages": []}),
    ), patch(
        "app.graph.workflow.get_session",
        return_value=session,
    ), patch(
        "app.graph.workflow.generate_plan",
        new=fake_generate_plan,
    ), patch(
        "app.graph.workflow.adispatch_custom_event",
        new=AsyncMock(),
    ):
        await run_workflow(
            request=make_request(),
            intent=TravelIntent(avoid_places=["总统府"]),
        )

    passed_attractions = fake_generate_plan.await_args.kwargs["attractions"]
    assert [item.name for item in passed_attractions] == ["玄武湖", "夫子庙"]


@pytest.mark.asyncio
async def test_empty_avoid_places_keeps_all_candidates():
    candidates = [
        make_attraction("夫子庙"),
        make_attraction("总统府"),
        make_attraction("玄武湖"),
    ]
    session = {
        "attractions": candidates,
        "hotels": [],
        "weather": [],
    }
    fake_generate_plan = AsyncMock(return_value=({"attractions": []}, 0))

    with patch(
        "app.graph.workflow.agent.ainvoke",
        new=AsyncMock(return_value={"messages": []}),
    ), patch(
        "app.graph.workflow.get_session",
        return_value=session,
    ), patch(
        "app.graph.workflow.generate_plan",
        new=fake_generate_plan,
    ), patch(
        "app.graph.workflow.adispatch_custom_event",
        new=AsyncMock(),
    ):
        await run_workflow(
            request=make_request(),
            intent=TravelIntent(avoid_places=[]),
        )

    passed_attractions = fake_generate_plan.await_args.kwargs["attractions"]
    assert passed_attractions == candidates


@pytest.mark.asyncio
async def test_all_candidates_filtered_returns_fallback_without_generating_plan():
    candidates = [
        make_attraction("夫子庙"),
        make_attraction("总统府"),
    ]
    session = {
        "attractions": candidates,
        "hotels": [],
        "weather": [],
    }
    fake_generate_plan = AsyncMock()

    with patch(
        "app.graph.workflow.agent.ainvoke",
        new=AsyncMock(return_value={"messages": []}),
    ), patch(
        "app.graph.workflow.get_session",
        return_value=session,
    ), patch(
        "app.graph.workflow.generate_plan",
        new=fake_generate_plan,
    ), patch(
        "app.graph.workflow.adispatch_custom_event",
        new=AsyncMock(),
    ):
        result = await run_workflow(
            request=make_request(),
            intent=TravelIntent(avoid_places=["夫子庙", "总统府"]),
        )

    assert result["trip_plan"]["attractions"] == []
    assert "景点数据暂不可用" in result["trip_plan"]["suggestion"]
    fake_generate_plan.assert_not_awaited()


@pytest.mark.asyncio
async def test_filtering_does_not_mutate_original_candidates_list():
    candidates = [
        make_attraction("夫子庙"),
        make_attraction("总统府"),
        make_attraction("玄武湖"),
    ]
    original_candidates = list(candidates)
    session = {
        "attractions": candidates,
        "hotels": [],
        "weather": [],
    }

    with patch(
        "app.graph.workflow.agent.ainvoke",
        new=AsyncMock(return_value={"messages": []}),
    ), patch(
        "app.graph.workflow.get_session",
        return_value=session,
    ), patch(
        "app.graph.workflow.generate_plan",
        new=AsyncMock(return_value=({"attractions": []}, 0)),
    ), patch(
        "app.graph.workflow.adispatch_custom_event",
        new=AsyncMock(),
    ):
        await run_workflow(
            request=make_request(),
            intent=TravelIntent(avoid_places=["总统府"]),
        )

    assert candidates == original_candidates
    assert [item.name for item in candidates] == ["夫子庙", "总统府", "玄武湖"]
