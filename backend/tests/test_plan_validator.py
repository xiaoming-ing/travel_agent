from app.planning.validator import (
    remove_cross_day_duplicates,
    validate_plan,
)
from app.schemas import TravelIntent


def make_plan() -> dict:
    return {
        "destination": "南京",
        "start_date": "2026-10-01",
        "end_date": "2026-10-02",
        "trip_days": 2,
        "budget": {
            "attractions": 100,
            "hotel": 600,
            "meals": 300,
            "transport": 200,
        },
        "attractions": [
            {"name": "夫子庙", "description": "秦淮文化"},
            {"name": "玄武湖", "description": "城市湖泊"},
        ],
        "daily_plans": [
            {
                "day": 1,
                "date": "2026-10-01",
                "description": "历史文化",
                "attraction_names": ["夫子庙"],
            },
            {
                "day": 2,
                "date": "2026-10-02",
                "description": "湖边休闲",
                "attraction_names": ["玄武湖"],
            },
        ],
    }


def test_validate_plan_accepts_valid_plan():
    result = validate_plan(
        make_plan(),
        TravelIntent(must_visit=["夫子庙"], budget_limit=1500),
    )

    assert result.passed is True
    assert result.violations == []


def test_validate_plan_reports_key_violations():
    plan = make_plan()
    plan["attractions"] = [{"name": "总统府", "description": "爬山体验"}]
    plan["daily_plans"][0]["attraction_names"] = ["总统府", "玄武湖", "紫金山"]
    plan["daily_plans"][1]["attraction_names"] = ["玄武湖"]
    plan["budget"]["hotel"] = 3000

    result = validate_plan(
        plan,
        TravelIntent(
            must_visit=["夫子庙"],
            avoid_places=["总统府"],
            pace="relaxed",
            excluded_activities=["爬山"],
            budget_limit=1000,
        ),
    )

    assert result.passed is False
    assert any("缺少必去景点：夫子庙" in item for item in result.violations)
    assert any("避开的景点：总统府" in item for item in result.violations)
    assert any("景点跨天重复：玄武湖" in item for item in result.violations)
    assert any("未在景点列表中的地点：紫金山" in item for item in result.violations)
    assert any("最多应为 2 个" in item for item in result.violations)
    assert any("禁止的活动：爬山" in item for item in result.violations)
    assert any("超过上限" in item for item in result.violations)


def test_remove_cross_day_duplicates_does_not_mutate_original():
    plan = make_plan()
    plan["daily_plans"][1]["attraction_names"] = ["夫子庙", "玄武湖"]

    repaired = remove_cross_day_duplicates(plan)

    assert repaired["daily_plans"][1]["attraction_names"] == ["玄武湖"]
    assert plan["daily_plans"][1]["attraction_names"] == ["夫子庙", "玄武湖"]
