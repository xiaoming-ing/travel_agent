from app.schemas import TravelIntent
import pytest

def test_travel_intent_defaults():
    intent = TravelIntent()

    assert intent.must_visit == []
    assert intent.avoid_places == []
    assert intent.themes == []
    assert intent.pace == "normal"
    assert intent.activity_environment == "mixed"
    assert intent.traveler_types == []
    assert intent.budget_limit is None
    assert intent.budget_level is None
    assert intent.ambiguities == []

def test_list_normalization():
    intent = TravelIntent(
        must_visit=[" 夫子庙 ", "", "夫子庙", "中山陵 "],
        dietary_restrictions=[" 海鲜", "花生 ", "海鲜"],
    )

    assert intent.must_visit == ["夫子庙", "中山陵"]
    assert intent.dietary_restrictions == ["海鲜", "花生"]

@pytest.mark.parametrize( # 用多组输入重复执行同一个测试函数
    "field,value",
    [
        ("pace","随便"),
        ("activity_environment","海底"),
        ("budget_level","非常贵"),
        ("traveler_types",["外星人"]),
    ],
)
def test_rejects_invalid_enum(field,value):
    with pytest.raises(ValueError):
        TravelIntent(**{field:value}) # **{field: value},动态构建关键字参数{"pace","随便"}会展开成TravelIntent(pace="随便")

@pytest.mark.parametrize("budget",[0,-100])
def test_rejects_non_positive_budget(budget):
    with pytest.raises(ValueError):
        TravelIntent(budget_limit=budget)

def test_detect_visit_conflict():
    intent = TravelIntent(
        must_visit=[" 夫子庙 "],
        avoid_places=["夫子庙"],
    )

    assert len(intent.ambiguities) == 1
    assert "夫子庙" in intent.ambiguities[0]
    assert "必去" in intent.ambiguities[0]