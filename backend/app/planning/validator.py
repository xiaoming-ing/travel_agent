"""Deterministic validation and safe repairs for generated trip plans."""

from __future__ import annotations

import copy
from collections import Counter
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel, Field

from app.schemas import TravelIntent


class ValidationResult(BaseModel):
    passed: bool
    violations: list[str] = Field(default_factory=list)


def _normalize_name(value: object) -> str:
    return str(value or "").strip()


def _parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def validate_plan(plan: dict[str, Any], intent: TravelIntent) -> ValidationResult:
    violations: list[str] = []
    declared_names = {
        _normalize_name(item.get("name"))
        for item in plan.get("attractions", [])
        if isinstance(item, dict) and _normalize_name(item.get("name"))
    }

    daily_plans = plan.get("daily_plans", [])
    scheduled_names: list[str] = []
    names_by_day: list[set[str]] = []
    for daily in daily_plans:
        day_names = [
            _normalize_name(name)
            for name in daily.get("attraction_names", [])
            if _normalize_name(name)
        ]
        scheduled_names.extend(day_names)
        names_by_day.append(set(day_names))

        unknown = sorted(set(day_names) - declared_names)
        for name in unknown:
            violations.append(f"每日行程引用了未在景点列表中的地点：{name}")

        if intent.pace == "relaxed" and len(day_names) > 2:
            violations.append(
                f"轻松节奏下 Day {daily.get('day')} 安排了 {len(day_names)} 个景点，最多应为 2 个"
            )

    scheduled_set = set(scheduled_names)
    for name in intent.must_visit:
        if _normalize_name(name) not in scheduled_set:
            violations.append(f"缺少必去景点：{name}")

    for name in intent.avoid_places:
        if _normalize_name(name) in scheduled_set:
            violations.append(f"安排了明确避开的景点：{name}")

    day_occurrences = Counter(
        name for day_names in names_by_day for name in day_names
    )
    for name, count in sorted(day_occurrences.items()):
        if count > 1:
            violations.append(f"景点跨天重复：{name}")

    searchable_text = "\n".join(
        [
            *scheduled_names,
            *[
                str(item.get("description", ""))
                for item in plan.get("attractions", [])
                if isinstance(item, dict)
            ],
            *[
                str(item.get("description", ""))
                for item in daily_plans
                if isinstance(item, dict)
            ],
        ]
    )
    for activity in intent.excluded_activities:
        if activity.strip() and activity.strip() in searchable_text:
            violations.append(f"安排了明确禁止的活动：{activity}")

    if intent.budget_limit is not None:
        budget = plan.get("budget", {})
        total = sum(
            float(budget.get(key, 0) or 0)
            for key in ("attractions", "hotel", "meals", "transport")
        )
        if total > intent.budget_limit:
            violations.append(
                f"预算总额 {total:g} 元超过上限 {intent.budget_limit} 元"
            )

    trip_days = plan.get("trip_days")
    if isinstance(trip_days, int) and len(daily_plans) != trip_days:
        violations.append(
            f"每日行程数量 {len(daily_plans)} 与行程天数 {trip_days} 不一致"
        )

    actual_days = [item.get("day") for item in daily_plans]
    expected_days = list(range(1, len(daily_plans) + 1))
    if actual_days != expected_days:
        violations.append("Day 序号必须从 1 开始连续递增")

    start_date = _parse_date(plan.get("start_date"))
    end_date = _parse_date(plan.get("end_date"))
    if start_date is not None and end_date is not None:
        expected_trip_days = (end_date - start_date).days + 1
        if trip_days != expected_trip_days:
            violations.append(
                f"行程天数 {trip_days} 与起止日期计算结果 {expected_trip_days} 不一致"
            )
        expected_dates = [
            start_date + timedelta(days=index) for index in range(len(daily_plans))
        ]
        actual_dates = [_parse_date(item.get("date")) for item in daily_plans]
        if actual_dates != expected_dates:
            violations.append("每日行程日期必须从开始日期起连续排列")

    return ValidationResult(passed=not violations, violations=violations)


def remove_cross_day_duplicates(plan: dict[str, Any]) -> dict[str, Any]:
    """Keep the first occurrence of each attraction and return a copied plan."""
    repaired = copy.deepcopy(plan)
    seen: set[str] = set()
    for daily in repaired.get("daily_plans", []):
        unique_names: list[str] = []
        for name in daily.get("attraction_names", []):
            normalized = _normalize_name(name)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_names.append(name)
        daily["attraction_names"] = unique_names
    return repaired
