import re
from typing import Literal

from app.schemas import TravelIntent


def find_visit_conflicts(intent: TravelIntent) -> list[str]:
    avoided = set(intent.avoid_places)
    return [place for place in intent.must_visit if place in avoided]


def resolve_visit_conflict(
    intent: TravelIntent,
    place: str,
    decision: Literal["visit", "avoid"],
) -> TravelIntent:
    data = intent.model_dump()
    if decision == "visit":
        data["avoid_places"] = [item for item in data["avoid_places"] if item != place]
    elif decision == "avoid":
        data["must_visit"] = [item for item in data["must_visit"] if item != place]
    else:
        raise ValueError(f"未知的冲突处理决定：{decision}")
    conflict_message = f"地点‘{place}’同时出现在必去和不想去列表中"
    data["ambiguities"] = [
        item for item in data["ambiguities"] if item != conflict_message
    ]
    return TravelIntent.model_validate(data)


def parse_visit_decision(answer: str) -> Literal["visit", "avoid"] | None:
    normalized = answer.strip()
    if normalized in {"去", "要去", "保留"}:
        return "visit"
    if normalized in {"不去", "避开", "删除"}:
        return "avoid"
    return None


def find_budget_ambiguities(intent: TravelIntent) -> list[str]:
    return [item for item in intent.ambiguities if "预算" in item]


def resolve_budget_answer(
    intent: TravelIntent,
    answer: str,
    trip_days: int,
) -> TravelIntent | None:
    normalized = answer.strip()
    amounts = re.findall(r"\d+", normalized.replace(",", ""))
    amount = int(amounts[0]) if amounts else None

    if "人均" in normalized:
        return None
    if any(marker in normalized for marker in ("每天", "每日")):
        if amount is None:
            return None
        budget_limit = amount * trip_days
    elif any(marker in normalized for marker in ("总预算", "全程", "总额", "一共")):
        budget_limit = amount if amount is not None else intent.budget_limit
    elif amount is not None:
        budget_limit = amount
    else:
        return None

    if budget_limit is None or budget_limit <= 0:
        return None
    data = intent.model_dump()
    data["budget_limit"] = budget_limit
    data["ambiguities"] = [item for item in data["ambiguities"] if "预算" not in item]
    return TravelIntent.model_validate(data)


def merge_travel_intents(base: TravelIntent, update: TravelIntent) -> TravelIntent:
    data = base.model_dump()
    list_fields = (
        "must_visit",
        "avoid_places",
        "themes",
        "traveler_types",
        "accessibility_needs",
        "dietary_restrictions",
        "hotel_requirements",
        "time_requirements",
        "excluded_activities",
        "special_requests",
        "ambiguities",
    )
    for field in list_fields:
        data[field] = list(dict.fromkeys([*data[field], *getattr(update, field)]))

    if update.must_visit:
        data["avoid_places"] = [
            item for item in data["avoid_places"] if item not in update.must_visit
        ]
    if update.avoid_places:
        data["must_visit"] = [
            item for item in data["must_visit"] if item not in update.avoid_places
        ]
    if update.pace != "normal":
        data["pace"] = update.pace
    if update.activity_environment != "mixed":
        data["activity_environment"] = update.activity_environment
    if update.budget_limit is not None:
        data["budget_limit"] = update.budget_limit
    if update.budget_level is not None:
        data["budget_level"] = update.budget_level

    return TravelIntent.model_validate(data)
