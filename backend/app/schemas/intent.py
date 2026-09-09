from pydantic import BaseModel,Field,field_validator,model_validator
from typing import Literal

# 继承BaseModel,这个class就获得了自动校验、类型转换、JSON Schema生成等能力
class TravelIntent(BaseModel):
    must_visit: list[str] = Field(default_factory=list,description="必去景点")
    avoid_places: list[str] = Field(default_factory=list,description="不想去的景点")
    themes: list[str] = Field(default_factory=list,description="旅行主题")
    pace: Literal["relaxed","normal", "packed"] = Field(default="normal",description="旅行节奏")
    activity_environment: Literal["indoor", "outdoor", "mixed"] = Field(default="mixed",description="活动环境")
    traveler_types: list[Literal["elderly", "child", "infant", "couple", "solo"]] = Field(default_factory=list,description="旅行者类型")
    accessibility_needs: list[str]= Field(default_factory=list,description="无障碍需求")
    dietary_restrictions: list[str]= Field(default_factory=list,description="饮食限制")
    budget_limit: int | None = Field(default=None,gt=0,description="所有同行者在整个行程中的总预算上限，单位为人民币元")
    budget_level: Literal["economy","normal","premium"] | None = Field(default=None,description="预算等级")
    hotel_requirements: list[str] = Field(default_factory=list,description="酒店要求")
    time_requirements: list[str]= Field(default_factory=list,description="时间限制")
    excluded_activities: list[str] = Field(default_factory=list,description="不想参与的活动")
    special_requests: list[str] = Field(default_factory=list,description="特殊要求")
    ambiguities: list[str] = Field(default_factory=list,description="模糊需求")

    @field_validator(
        "must_visit",
        "avoid_places",
        "themes",
        "accessibility_needs",
        "dietary_restrictions",
        "hotel_requirements",
        "time_requirements",
        "excluded_activities",
        "special_requests",
        "ambiguities",
    )
    @classmethod
    def normalize_text_list(cls, value: list[str]) -> list[str]:
        res = [i.strip() for i in value if i.strip()]
        return list(dict.fromkeys(res))


    @model_validator(mode="after")
    def detect_visit_conflicts(self):
        conflicts = set(self.must_visit) & set(self.avoid_places)
        for place in sorted(conflicts):
            message = f"地点‘{place}’同时出现在必去和不想去列表中"
            if message not in self.ambiguities: 
                self.ambiguities.append(message)
        return self
    

    
