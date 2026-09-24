from typing import Optional, TypedDict

from app.schemas import Attraction, FeedbackIntent, Hotel, TravelIntent, TripRequest


class ConversationState(TypedDict):
    request: TripRequest
    intent: TravelIntent
    trip_plan: Optional[dict]
    raw_attractions: list[Attraction]
    raw_hotels: list[Hotel]
    last_feedback: Optional[str]
    token_used: int
    revise_note: Optional[str]
    feedback_intent: Optional[FeedbackIntent]
    feedback_answer: Optional[str]
