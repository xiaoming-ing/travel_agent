from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.itinerary import (
      _build_itinerary_prompt,
      _format_hard_constraints,
      _format_soft_preferences,
)
from app.agents.itinerary import generate_plan
from app.schemas import Attraction, TravelIntent, TripPlan, TripRequest

def test_format_hard_constraints():
      intent = TravelIntent(
          must_visit=["夫子庙", "中山陵"],
          avoid_places=["总统府"],
          dietary_restrictions=["海鲜"],
          budget_limit=3000,
          excluded_activities=["爬山"],
          time_requirements=["第二天晚上看夜景"],
      )

      result = _format_hard_constraints(intent)

      assert result.splitlines() == [
          "- 必须安排：夫子庙、中山陵",
          "- 禁止安排地点：总统府",
          "- 饮食限制：海鲜",
          "- 总预算上限：3000 元",
          "- 禁止活动：爬山",
          "- 时间要求：第二天晚上看夜景",
      ]

def test_format_hard_constraints_returns_none_message_for_default_intent():
      result = _format_hard_constraints(TravelIntent())

      assert result == "无明确硬约束"


def test_format_soft_preferences():
      intent = TravelIntent(
          themes=["历史文化", "夜景"],
          pace="relaxed",
          activity_environment="outdoor",
          traveler_types=["elderly", "child"],
          accessibility_needs=["减少步行", "避免登高"],
          budget_level="economy",
          hotel_requirements=["安静", "含早餐"],
          special_requests=["适合拍照"],
      )

      result = _format_soft_preferences(intent)

      assert result.splitlines() == [
          "- 旅行主题：历史文化、夜景",
          "- 行程节奏：轻松",
          "- 活动环境：户外",
          "- 同行人：老人、儿童",
          "- 行动与无障碍偏好：减少步行、避免登高",
          "- 消费档次：经济",
          "- 酒店偏好：安静、含早餐",
          "- 其他偏好：适合拍照",
      ]


def test_format_soft_preferences_returns_none_message_for_default_intent():
      result = _format_soft_preferences(TravelIntent())

      assert result == "无明确软偏好"


def test_build_itinerary_prompt_contains_structured_intent():
      request = TripRequest(
          destination="南京",
          start_date=date(2026, 10, 1),
          end_date=date(2026, 10, 3),
          preferences=["历史文化"],
          extra_requirements="希望整体安排得舒服一些",
      )
      intent = TravelIntent(
          must_visit=["夫子庙"],
          dietary_restrictions=["海鲜"],
          pace="relaxed",
          traveler_types=["elderly"],
      )
      attractions = [
          Attraction(
              name="夫子庙",
              address="南京市秦淮区",
              longitude=118.79,
              latitude=32.02,
              description="秦淮文化地标",
          )
      ]

      prompt = _build_itinerary_prompt(
          request=request,
          intent=intent,
          attractions=attractions,
          weather=[],
          hotel_price_range="300-500元",
      )

      assert "【必须满足的硬约束】" in prompt
      assert "- 必须安排：夫子庙" in prompt
      assert "- 饮食限制：海鲜" in prompt
      assert "【尽量满足的软偏好】" in prompt
      assert "- 行程节奏：轻松" in prompt
      assert "- 同行人：老人" in prompt
      assert "{hard_constraints}" not in prompt
      assert "{soft_preferences}" not in prompt


def make_generated_plan(attraction_name: str) -> TripPlan:
      return TripPlan.model_validate({
          "destination": "南京",
          "start_date": "2026-10-01",
          "end_date": "2026-10-01",
          "trip_days": 1,
          "suggestion": "建议",
          "budget": {"attractions": 0, "hotel": 300, "meals": 100, "transport": 50},
          "attractions": [{
              "name": attraction_name,
              "address": f"{attraction_name}地址",
              "longitude": 118.0,
              "latitude": 32.0,
              "description": "景点简介",
          }],
          "daily_plans": [{
              "day": 1,
              "date": "2026-10-01",
              "description": "一日游",
              "transport": "公共交通",
              "accommodation": "经济型酒店",
              "attraction_names": [attraction_name],
              "meals": {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐"},
          }],
          "hotels": [],
          "weather_summary": "暂无天气",
      })


@pytest.mark.asyncio
async def test_generate_plan_repairs_constraint_violation_at_most_once():
      request = TripRequest(
          destination="南京",
          start_date=date(2026, 10, 1),
          end_date=date(2026, 10, 1),
      )
      raw_attractions = [
          Attraction(
              name=name,
              address=f"{name}地址",
              longitude=118.0,
              latitude=32.0,
              description="景点简介",
          )
          for name in ("玄武湖", "夫子庙")
      ]
      planner = MagicMock()
      planner.ainvoke = AsyncMock(side_effect=[
          {"parsed": make_generated_plan("玄武湖"), "raw": None},
          {"parsed": make_generated_plan("夫子庙"), "raw": None},
      ])
      fake_llm = MagicMock()
      fake_llm.with_structured_output.return_value = planner

      with patch("app.agents.itinerary.llm", fake_llm), patch(
          "app.agents.itinerary.retrieve_for_attractions",
          new=AsyncMock(return_value={}),
      ):
          plan, _ = await generate_plan(
              request=request,
              intent=TravelIntent(must_visit=["夫子庙"]),
              attractions=raw_attractions,
              hotels=[],
              weather=[],
          )

      assert planner.ainvoke.await_count == 2
      assert plan["daily_plans"][0]["attraction_names"] == ["夫子庙"]
      assert "暂未完全满足" not in plan["suggestion"]


@pytest.mark.asyncio
async def test_generate_plan_reports_violations_after_single_failed_repair():
      request = TripRequest(
          destination="南京",
          start_date=date(2026, 10, 1),
          end_date=date(2026, 10, 1),
      )
      raw_attraction = Attraction(
          name="玄武湖",
          address="玄武湖地址",
          longitude=118.0,
          latitude=32.0,
          description="景点简介",
      )
      planner = MagicMock()
      planner.ainvoke = AsyncMock(side_effect=[
          {"parsed": make_generated_plan("玄武湖"), "raw": None},
          {"parsed": make_generated_plan("玄武湖"), "raw": None},
      ])
      fake_llm = MagicMock()
      fake_llm.with_structured_output.return_value = planner

      with patch("app.agents.itinerary.llm", fake_llm), patch(
          "app.agents.itinerary.retrieve_for_attractions",
          new=AsyncMock(return_value={}),
      ):
          plan, _ = await generate_plan(
              request=request,
              intent=TravelIntent(must_visit=["夫子庙"]),
              attractions=[raw_attraction],
              hotels=[],
              weather=[],
          )

      assert planner.ainvoke.await_count == 2
      assert "暂未完全满足" in plan["suggestion"]
      assert "缺少必去景点：夫子庙" in plan["suggestion"]
