"""feedback_node 后的路由逻辑：should_revise 决定走 revise 还是 END。"""
from types import SimpleNamespace

import pytest
from langgraph.graph import END
from app.graph import conversation
from app.graph.conversation import build_feedback_question, should_revise


def test_satisfied_feedback_ends_conversation():
    assert should_revise({"last_feedback": "满意"}) == END
    assert should_revise({"last_feedback": "done"}) == END
    assert should_revise({"last_feedback": " OK "}) == END  # 大小写/空格不敏感


def test_unsatisfied_feedback_goes_to_revise():
    assert should_revise({"last_feedback": "Day2换成自然风光"}) == "revise"


def test_missing_feedback_goes_to_revise():
    assert should_revise({}) == "revise"


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
