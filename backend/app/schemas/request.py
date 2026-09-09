"""
前端表单发过来的数据。
用Pydantic做校验：必填字段漏了会自动返回422，不用自己写if判断。
"""

from datetime import date
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

Transport = Literal["公共交通", "自驾", "打车", "步行"]
Accommodation = Literal[
    "经济型酒店",
    "舒适型酒店",
    "豪华型酒店",
    "民宿",
]

Preference = Literal[
    "历史文化",
    "自然风光",
    "美食",
    "购物",
    "艺术",
    "休闲",
    "亲子",
]


class TripRequest(BaseModel):
    """用户提交的旅行需求"""

    #目的地与日期
    destination: str = Field(..., description="目的地城市，如‘南京’")
    start_date: date = Field(..., description="开始日期，前端传'YYYY-MM-DD'字符串即可")
    end_date: date = Field(..., description="结束日期")

    # 偏好设置
    # 用字面量限制取值范围，LLM输出时也有据可依
    transport: Transport = Field(default="公共交通", description="交通方式：公共交通/自驾/打车/步行")
    accommodation: Accommodation = Field(default="经济型酒店", description="住宿偏好：经济型酒店/舒适型酒店/豪华型酒店/民宿")
    preferences: List[Preference] = Field(default_factory=list, description="旅行偏好（多选）:历史文化/自然风光/美食/购物/艺术/休闲/亲子")

    # 额外要求
    extra_requirements: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="自由文本，如‘想看升旗，对海鲜过敏’，最多 1000 字",
    )

    @property
    def trip_days(self) -> int:
        """计算旅行天数（含头尾）"""
        return (self.end_date - self.start_date).days + 1

    @model_validator(mode="after") # 检查整个对象的装饰器，validator的返回值，就是最终保存到模型里的值
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        if self.trip_days > 15:
            raise ValueError("行程不能超过15天")
        return self

    @field_validator("destination") # 检查某一字段
    @classmethod
    def validate_destination(cls, value: str) -> str:
        destination = value.strip()
        if not destination:
            raise ValueError("目的地不能为空")
        if len(destination) > 50:
            raise ValueError("目的地不能超过50个字符")
        return destination

    @field_validator("extra_requirements")
    @classmethod
    def normalize_extra_requirements(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return value.strip() or None


class ChatStartBody(BaseModel):
    """开始旅行规划的请求体。"""

    request: TripRequest


class ChatResumeBody(BaseModel):
    """恢复会话的请求体。"""

    thread_id: str = Field(min_length=36, max_length=36)
    answer: str = Field(min_length=1, max_length=2000)

    @field_validator("thread_id")
    @classmethod
    def validate_thread_id(cls, value: str) -> str:
        try:
            parsed = UUID(value)
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("thread_id 必须是合法的 UUID4") from exc
        if parsed.version != 4:
            raise ValueError("thread_id 必须是合法的 UUID4")
        return str(parsed)

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, value: str) -> str:
        answer = value.strip()
        if not answer:
            raise ValueError("回答不能为空")
        return answer


class KnowledgeUploadBody(BaseModel):
    """上传一篇知识库资料的请求体。"""

    city: str = Field(min_length=1, max_length=50)
    source: str = Field(default="", max_length=200)
    content: str = Field(min_length=1, max_length=50_000)

    @field_validator("city", "source", "content", mode="before")
    @classmethod
    def strip_text_fields(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value
