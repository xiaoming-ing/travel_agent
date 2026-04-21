"""把常用类型集中导出，其他模块import一行就够了"""

from app.schemas.request import TripRequest
from app.schemas.response import (
    TripPlan,
    Attraction,
    Hotel,
    MealPlan,
    DailyPlan,
    BudgetBreakdown
)

__all__ = [
    "TripRequest",
    "TripPlan",
    "Attraction",
    "Hotel",
    "MealPlan",
    "DailyPlan",
    "BudgetBreakdown"
]