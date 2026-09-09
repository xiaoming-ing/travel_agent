"""把常用类型集中导出，其他模块import一行就够了"""

from app.schemas.request import (
    ChatResumeBody,
    ChatStartBody,
    KnowledgeUploadBody,
    TripRequest,
)
from app.schemas.response import (
    TripPlan,
    Attraction,
    Hotel,
    MealPlan,
    DailyPlan,
    BudgetBreakdown
)

from app.schemas.intent import (
    TravelIntent,
)

__all__ = [
    "TripRequest",
    "ChatStartBody",
    "ChatResumeBody",
    "KnowledgeUploadBody",
    "TripPlan",
    "Attraction",
    "Hotel",
    "MealPlan",
    "DailyPlan",
    "BudgetBreakdown",
    "TravelIntent"
]
