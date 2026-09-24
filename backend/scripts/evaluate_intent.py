"""Run the live intent-recognition evaluation set.

Usage from backend/: python scripts/evaluate_intent.py
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import date
from pathlib import Path
from typing import Any

from app.planning.intent_parser import parse_travel_intent
from app.schemas import TripRequest


CASES_PATH = Path(__file__).parents[1] / "evals" / "intent_cases.json"


def _matches_expected(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    for field, expected_value in expected.items():
        actual_value = actual.get(field)
        if isinstance(expected_value, list):
            if not set(expected_value).issubset(set(actual_value or [])):
                return False
        elif actual_value != expected_value:
            return False
    return True


def _contains_expected(actual: dict[str, Any], expected: dict[str, list[str]]) -> bool:
    for field, fragments in expected.items():
        values = [str(value) for value in actual.get(field, [])]
        if not all(any(fragment in value for value in values) for fragment in fragments):
            return False
    return True


def _avoids_forbidden(actual: dict[str, Any], forbidden: dict[str, list[str]]) -> bool:
    for field, fragments in forbidden.items():
        values = [str(value) for value in actual.get(field, [])]
        if any(any(fragment in value for value in values) for fragment in fragments):
            return False
    return True


async def main() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    passed = 0
    elapsed: list[float] = []

    for case in cases:
        request = TripRequest(
            destination="南京",
            start_date=date(2027, 10, 1),
            end_date=date(2027, 10, 3),
            extra_requirements=case["text"],
        )
        started = time.perf_counter()
        intent = await parse_travel_intent(request)
        elapsed.append(time.perf_counter() - started)
        actual = intent.model_dump()
        ok = (
            _matches_expected(actual, case.get("expected", {}))
            and _contains_expected(actual, case.get("contains", {}))
            and _avoids_forbidden(actual, case.get("forbidden_contains", {}))
        )
        passed += int(ok)
        print(f"[{'PASS' if ok else 'FAIL'}] {case['name']}")
        if not ok:
            print(json.dumps(actual, ensure_ascii=False, indent=2))

    accuracy = passed / len(cases) if cases else 0
    average_seconds = sum(elapsed) / len(elapsed) if elapsed else 0
    print(f"\n通过率：{passed}/{len(cases)} = {accuracy:.1%}")
    print(f"平均耗时：{average_seconds:.2f}s")
    if accuracy < 0.9:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
