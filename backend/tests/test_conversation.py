"""feedback_node 后的路由逻辑：should_revise 决定走 revise 还是 END。"""
from types import SimpleNamespace

import pytest
from langgraph.graph import END
from app.graph import conversation
from app.graph.conversation import (
    build_feedback_question,
    classify_feedback_by_rule,
    clarify_node,
    find_visit_conflicts,
    merge_travel_intents,
    parse_visit_decision,
    resolve_budget_answer,
    resolve_visit_conflict,
    should_revise,
)
from app.schemas import TripRequest,TravelIntent
from datetime import date,timedelta


def test_satisfied_feedback_ends_conversation():
    assert should_revise({"last_feedback": "满意"}) == END
    assert should_revise({"last_feedback": "done"}) == END
    assert should_revise({"last_feedback": " OK "}) == END  # 大小写/空格不敏感


def test_unsatisfied_feedback_goes_to_revise():
    assert should_revise({"last_feedback": "Day2换成自然风光"}) == "revise"


def test_missing_feedback_goes_to_revise():
    assert should_revise({}) == "revise"


def test_feedback_rule_prioritizes_revision_over_polite_agreement():
    result = classify_feedback_by_rule("可以，但第二天太赶了，轻松一点")

    assert result is not None
    assert result.action == "revise"
    assert result.revision_type == "pace"


def test_feedback_rule_distinguishes_finish_and_question():
    assert classify_feedback_by_rule("挺好的").action == "finish"
    assert classify_feedback_by_rule("挺好的，就这样").action == "finish"
    assert classify_feedback_by_rule("不用改了").action == "finish"
    assert classify_feedback_by_rule("第二天住哪家酒店？").action == "question"


def test_merge_travel_intents_keeps_original_constraints():
    merged = merge_travel_intents(
        TravelIntent(
            must_visit=["夫子庙"],
            dietary_restrictions=["海鲜"],
        ),
        TravelIntent(
            avoid_places=["总统府"],
            pace="relaxed",
        ),
    )

    assert merged.must_visit == ["夫子庙"]
    assert merged.avoid_places == ["总统府"]
    assert merged.dietary_restrictions == ["海鲜"]
    assert merged.pace == "relaxed"


def test_resolve_budget_answer_converts_daily_budget_to_trip_total():
    intent = TravelIntent(
        budget_limit=1000,
        ambiguities=["需确认预算是全程总额、人均金额还是每日金额"],
    )

    result = resolve_budget_answer(intent, "每天 1000 元", trip_days=3)

    assert result is not None
    assert result.budget_limit == 3000
    assert result.ambiguities == []


@pytest.mark.asyncio
async def test_feedback_question_uses_llm_context(monkeypatch):
    calls = []

    class FakeFeedbackLLM:
        async def ainvoke(self, messages):
            calls.append(messages)
            return SimpleNamespace(content="第二天已经重新调过了，你看下现在顺不顺。")

    monkeypatch.setattr(conversation,"feedback_llm",FakeFeedbackLLM())

    question = await build_feedback_question(
        "修改一下第二天行程",
        {
            "destination":"南京",
            "trip_days":2,
            "daily_plans":[
                {"day":1,"attraction_names":["夫子庙"]},
                {"day":2,"attraction_names":["玄武湖","中山陵"]},
            ],
            "hotels":[],
        },
    )

    assert question == "第二天已经重新调过了，你看下现在顺不顺。"
    assert calls
    prompt = calls[0][1].content
    assert "修改一下第二天行程" in prompt
    assert "Day 2：玄武湖、中山陵" in prompt


@pytest.mark.asyncio
async def test_feedback_question_falls_back_when_llm_fails(monkeypatch):
    class FailingFeedbackLLM:
        async def ainvoke(self, messages):
            raise RuntimeError("llm unavailable")

    monkeypatch.setattr(conversation,"feedback_llm",FailingFeedbackLLM())

    question = await build_feedback_question("修改一下第二天行程",None)

    assert "行程已生成" not in question
    assert "满意" not in question
    assert "done" not in question
    assert "调了一版" in question

@pytest.mark.asyncio
async def test_empty_preferences_do_not_trigger_clarification():
    request = TripRequest(
        destination="南京",
        start_date=date.today() + timedelta(days=1),
        end_date=date.today() + timedelta(days=3),
        preferences=[],
    )
    result = await clarify_node({
        "request": request,
        "intent": TravelIntent(),
    })

    assert result == {}

def test_find_visit_conflicts():
    intent = TravelIntent(
        must_visit=["夫子庙","中山陵"],
        avoid_places=["总统府", "夫子庙"],
    )
    assert find_visit_conflicts(intent) == ["夫子庙"]

def test_find_visit_conflicts_returns_empty_list():
    intent = TravelIntent(
        must_visit=["夫子庙"],
        avoid_places=["总统府"],
    )

    assert find_visit_conflicts(intent) == []

def test_resolve_visit_conflict_keeps_visit():
    intent = TravelIntent(
        must_visit=["夫子庙"],
        avoid_places=["夫子庙"],
    )

    result = resolve_visit_conflict(intent, "夫子庙", "visit")

    assert result.must_visit == ["夫子庙"]
    assert result.avoid_places == []
    assert result.ambiguities == []

    # 原对象不能被修改
    assert intent.avoid_places == ["夫子庙"]

def test_resolve_visit_conflict_keeps_avoid():
    intent = TravelIntent(
        must_visit=["夫子庙"],
        avoid_places=["夫子庙"],
    )

    result = resolve_visit_conflict(intent, "夫子庙", "avoid")

    assert result.must_visit == []
    assert result.avoid_places == ["夫子庙"]
    assert result.ambiguities == []

    assert intent.must_visit == ["夫子庙"]

def test_resolve_visit_conflict_rejects_unknown_decision():
    intent = TravelIntent(
        must_visit=["夫子庙"],
        avoid_places=["夫子庙"],
    )

    with pytest.raises(ValueError, match="未知的冲突处理决定"):
        resolve_visit_conflict(intent, "夫子庙", "unknown")

@pytest.mark.asyncio
async def test_clarify_node_resolves_visit_conflict(monkeypatch): # monkeypatch是pytest自带的，在测试过程中，临时修改某个变量、函数、环境变量、对象等属性；测试结束后自动恢复
    monkeypatch.setattr(conversation,"interrupt",lambda payload: "去")
    result = await clarify_node({
        "request":TripRequest(
            destination="南京",
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=3),
        ),
        "intent": TravelIntent(
            must_visit=["夫子庙"],
            avoid_places=["夫子庙"],
        ),
    })
    assert result["intent"].must_visit == ["夫子庙"]
    assert result["intent"].avoid_places == []
    assert result["intent"].ambiguities == []

@pytest.mark.asyncio
async def test_clarify_node_reasks_for_unknown_decision(monkeypatch):
    answers = iter(["随便", "不去"])
    payloads = []

    def fake_interrupt(payload):
        payloads.append(payload)
        return next(answers)

    monkeypatch.setattr(conversation, "interrupt", fake_interrupt)

    result = await clarify_node({
        "request": TripRequest(
            destination="南京",
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=3),
        ),
        "intent": TravelIntent(
            must_visit=["夫子庙"],
            avoid_places=["夫子庙"],
        ),
    })

    assert len(payloads) == 2
    assert result["intent"].must_visit == []
    assert result["intent"].avoid_places == ["夫子庙"]

@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("去", "visit"),
        (" 要去 ", "visit"),
        ("保留", "visit"),
        ("不去", "avoid"),
        ("避开", "avoid"),
        ("删除", "avoid"),
        ("随便", None),
    ],
)
def test_parse_visit_decision(answer, expected):
    assert parse_visit_decision(answer) == expected

@pytest.mark.asyncio
async def test_clarify_node_resolves_multiple_visit_conflicts(monkeypatch):
    answers = iter(["去", "不去"])

    monkeypatch.setattr(
        conversation,
        "interrupt",
        lambda payload: next(answers),
    )

    result = await clarify_node({
        "request": TripRequest(
            destination="南京",
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=3),
        ),
        "intent": TravelIntent(
            must_visit=["夫子庙", "中山陵"],
            avoid_places=["夫子庙", "中山陵"],
        ),
    })

    assert result["intent"].must_visit == ["夫子庙"]
    assert result["intent"].avoid_places == ["中山陵"]
    assert result["intent"].ambiguities == []
