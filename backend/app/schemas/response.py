"""
返回给前端的行程数据结构。
前端的地图、预算卡片、每日行程都按这个结构渲染。
每个子模型对应前端一个UI组件，改动时一一对应就好。
"""

from pydantic import BaseModel,Field
from typing import Optional,List
from datetime import date as _Date 

# 景点（给地图marker+每日行程卡片复用）
class Attraction(BaseModel):
    name: str = Field(...,description="景点名称，如‘北海公园’")
    address:str = Field(...,description="地址")
    # 高德返回的是“经度，纬度”字符串，这里拆成两个float方便前端地图直接用
    longitude:float = Field(...,description="经度")
    latitude:float = Field(...,description="纬度")
    duration_minutes:int = Field(default=120,description="建议游览时长（分钟）")
    ticket_price: float = Field(default=0,description="门票价格（元），免费填0")
    description: str = Field(...,description="景点亮点简介，1-2句即可")
    image_url:Optional[str] = Field(default=None,description="景点图片URL")


# 酒店
class Hotel(BaseModel):
    name:str
    address:str
    type:str = Field(...,description="酒店类型，如‘经济型酒店’")
    price_range:str = Field(...,description="价格区间，如‘300-500’")
    rating:float = Field(default=0,description="评分0-5")
    distance_note:str = Field(default="",description="距景点距离描述，如‘距景点中心3.2km’")
    longitude: float = Field(default=0.0, description="经度")
    latitude: float = Field(default=0.0, description="纬度")


# 餐饮（早/午/晚）
class MealPlan(BaseModel):
    breakfast: str = Field(...,description="早餐建议")
    lunch:str = Field(...,description="午餐建议")
    dinner: str = Field(...,description="午餐建议")


# 每日行程
class DailyPlan(BaseModel):
    day: int = Field(...,description="第几天，从1开始")
    date: _Date = Field(..., description="这天的具体日期")
    description: str = Field(...,description="当天行程，一句话概述")
    transport: str = Field(...,description="交通方式")
    accommodation: str = Field(...,description="住宿类型")
    # 用景点名称列表引用Attraction,而不是整个对象塞进来-避免数据重复
    attraction_names:List[str] = Field(...,description="当天要去的景点名称列表")
    meals:MealPlan

# 预算明细
class BudgetBreakdown(BaseModel):
    attractions: float = Field(...,description="景点门票总计")
    hotel: float = Field(...,description="酒店住宿总计")
    meals: float = Field(...,description="餐饮费用总计")
    transport: float = Field(...,description="交通费用总计")

    @property
    def total(self) -> float:
        """前端可以直接用total字段，不用自己加"""
        return self.attractions + self.hotel + self.meals + self.transport


# 最终返回给前端的完整行程
class TripPlan(BaseModel):
    """
    最终输出结构。整个API响应就是这个对象序列化成的JSON对象。
    字段顺序对应前端的视觉层级：先总览、再预算、再景点、再每日
    """
    destination: str
    start_date: _Date
    end_date: _Date
    trip_days: int

    # 顶部“建议”文本框的内容
    suggestion: str = Field(...,description="整体建议，2-3句话")

    # 预算卡片
    budget: BudgetBreakdown

    # 景点列表
    attractions: List[Attraction]

    # 每日行程
    daily_plans: List[DailyPlan]

    # 推荐酒店Top3（程序按交通方式+景点中心距离+评分综合排序后填入，不由LLM生成）
    hotels: List[Hotel] = Field(default_factory=list, description="推荐住宿Top3")

    # 天气信息
    weather_summary: str = Field(...,description="天气总结文本")
    