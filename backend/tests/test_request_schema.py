from app.schemas.request import ChatResumeBody, KnowledgeUploadBody, TripRequest
from pydantic import ValidationError
import pytest

def test_something_invalid():
    with pytest.raises(ValidationError):
        TripRequest(
            destination=" 南京 ",
            start_date="2026-08-28",
            end_date="2026-08-22"
        )

def test_valid_trip_days():
    request = TripRequest(
        destination="南京",
        start_date="2026-08-28",
        end_date="2026-08-30",
    )

    assert request.trip_days == 3    

@pytest.mark.parametrize(
    "destination",
    [
        "",
        "   ",
        "南"*51
    ]
)
def test_invalid_destination(destination):
    with pytest.raises(ValidationError):
        TripRequest(
            destination=destination,
            start_date="2026-08-28",
            end_date="2026-08-30",
        )

def test_destination_is_stripped():
    request = TripRequest(
        destination="  南京  ",
        start_date="2026-08-28",
        end_date="2026-08-30",
    )

    assert request.destination == "南京"

@pytest.mark.parametrize(
    "field, invalid_value",
    [
        ("transport", "直升机"),
        ("accommodation", "睡桥洞"),
        ("preferences", ["自然风光", "电子游戏"]),
    ],
)
def test_invalid_choice(field, invalid_value):
    data = {
        "destination": "南京",
        "start_date": "2026-08-28",
        "end_date": "2026-08-30",
    }
    data[field] = invalid_value

    with pytest.raises(ValidationError):
        TripRequest(**data)

def test_extra_requirements_max_length_is_allowed():
    request = TripRequest(
        destination="南京",
        start_date="2026-08-28",
        end_date="2026-08-30",
        extra_requirements="想" * 1000,
    )
    assert len(request.extra_requirements) == 1000

def test_extra_requirements_too_long():
    with pytest.raises(ValidationError) as exc_info:
        TripRequest(
            destination="南京",
            start_date="2026-08-28",
            end_date="2026-08-30",
            extra_requirements="想" * 1001,
        )

    assert exc_info.value.errors()[0]["loc"] == ("extra_requirements",)

def test_fifteen_day_trip_is_allowed():
    request = TripRequest(
        destination="南京",
        start_date="2026-08-01",
        end_date="2026-08-15",
    )

    assert request.trip_days == 15

def test_trip_longer_than_fifteen_days_is_rejected():
    with pytest.raises(ValidationError) as exc_info:
        TripRequest(
            destination="南京",
            start_date="2026-08-01",
            end_date="2026-08-16",
        )

    assert "不能超过15天" in str(exc_info.value)


def test_chat_resume_body_validates_and_normalizes_input():
    body = ChatResumeBody(
        thread_id="123e4567-e89b-42d3-a456-426614174000",
        answer="  请把第二天改轻松一点  ",
    )

    assert body.answer == "请把第二天改轻松一点"


@pytest.mark.parametrize(
    "data",
    [
        {"thread_id": "not-a-uuid", "answer": "修改行程"},
        {"thread_id": "123e4567-e89b-42d3-a456-426614174000", "answer": "   "},
        {"thread_id": "123e4567-e89b-42d3-a456-426614174000", "answer": "改" * 2001},
    ],
)
def test_chat_resume_body_rejects_invalid_input(data):
    with pytest.raises(ValidationError):
        ChatResumeBody(**data)


def test_knowledge_upload_body_strips_text():
    body = KnowledgeUploadBody(
        city="  南京  ",
        source="  本地攻略  ",
        content="  夫子庙适合夜游。  ",
    )

    assert body.city == "南京"
    assert body.source == "本地攻略"
    assert body.content == "夫子庙适合夜游。"


@pytest.mark.parametrize(
    "data",
    [
        {"city": "   ", "content": "有效内容"},
        {"city": "南京", "source": "来" * 201, "content": "有效内容"},
        {"city": "南京", "content": "   "},
        {"city": "南京", "content": "文" * 50_001},
    ],
)
def test_knowledge_upload_body_rejects_invalid_input(data):
    with pytest.raises(ValidationError):
        KnowledgeUploadBody(**data)
