"""
前端表单发过来的数据。
用Pydantic做校验：必填字段漏了会自动返回422，不用自己写if判断。
"""

from pydantic import BaseModel,Field
from datetime import date
from typing import List,Optional

class TripRequest(BaseModel):
    """用户提交的旅行需求"""

    #目的地与日期
    destination:str = Field(...,description="目的地城市，如‘南京’")
    start_date:date = Field(...,description="开始日期，前端传'YYYY-MM-DD'字符串即可")
    end_date:date = Field(...,description="结束日期")

    # 偏好设置
    # 用字面量限制取值范围，LLM输出时也有据可依
    transport: str = Field(default='公共交通',description="交通方式：公共交通/自驾/打车/步行")
    accommodation:str = Field(default="经济型酒店",description="住宿偏好：经济型酒店/舒适型酒店/豪华型酒店/名宿")
    preferences: List[str] = Field(default_factory=list,description="旅行偏好（多选）:历史文化/自然风光/美食/购物/艺术/休闲")

    # 额外要求
    extra_requirements:Optional[str] = Field(default=None,description="自由文本，如'想看升旗，对海鲜过敏‘")

    @property
    def trip_days(self) -> int:
        """计算旅行天数（含头尾）"""
        return (self.end_date - self.start_date).days + 1