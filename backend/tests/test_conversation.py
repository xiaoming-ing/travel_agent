"""feedback_node 后的路由逻辑：should_revise 决定走 revise 还是 END。"""
from langgraph.graph import END
from app.graph.conversation import should_revise


def test_satisfied_feedback_ends_conversation():
    assert should_revise({"last_feedback": "满意"}) == END
    assert should_revise({"last_feedback": "done"}) == END
    assert should_revise({"last_feedback": " OK "}) == END  # 大小写/空格不敏感


def test_unsatisfied_feedback_goes_to_revise():
    assert should_revise({"last_feedback": "Day2换成自然风光"}) == "revise"


def test_missing_feedback_goes_to_revise():
    assert should_revise({}) == "revise"
