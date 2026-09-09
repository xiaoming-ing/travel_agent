import pytest
from app.schemas import TravelIntent, TripRequest
from app.agents.intent import parse_travel_intent
from datetime import date
from unittest.mock import AsyncMock,MagicMock,patch

@pytest.mark.asyncio # 告诉pytest 下面这个测试函数是异步函数，请在事件循环中运行他
async def test_no_extra_requirements_returns_default_intent():
    request = TripRequest(
        destination="南京",
        start_date=date(2026,9,9),
        end_date=date(2026,9,12),
        extra_requirements=""
    )
    res = await parse_travel_intent(request)
    assert isinstance(res, TravelIntent)
    assert res == TravelIntent()

@pytest.mark.asyncio
async def test_parse_travel_intent_with_real_llm():
    request = TripRequest(
        destination="南京",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 3),
        extra_requirements=(
            "一定要去夫子庙，带老人，不吃海鲜,"
            "行程轻松一点，预算3000元"
        )
    )
    result = await parse_travel_intent(request)
    print(result.model_dump_json(indent=2))
    assert isinstance(result,TravelIntent)
    assert "夫子庙" in result.must_visit
    assert "elderly" in result.traveler_types

@pytest.mark.asyncio
async def test_llm_failure_returns_default_intent():
    request = TripRequest(
        destination="南京",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 3),
        extra_requirements="一定要去夫子庙",
    )
    fake_structured_llm = MagicMock()
    fake_structured_llm.ainvoke = AsyncMock(side_effect=RuntimeError("模拟模型调用失败"))

    fake_intent_llm = MagicMock()
    fake_intent_llm.with_structured_output.return_value = fake_structured_llm
    with patch(
        "app.agents.intent.intent_llm",
        fake_intent_llm,
    ):
        result = await parse_travel_intent(request)
    assert isinstance(result,TravelIntent)
    assert result == TravelIntent()
    fake_intent_llm.with_structured_output.assert_called_once_with(
        TravelIntent,
        include_raw=True,
    )
    fake_structured_llm.ainvoke.assert_awaited_once()
    