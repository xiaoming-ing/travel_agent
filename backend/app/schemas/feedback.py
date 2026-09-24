from typing import Literal

from pydantic import BaseModel


class FeedbackIntent(BaseModel):
    action: Literal["finish", "revise", "question", "unknown"]
    revision_type: Literal[
        "attractions",
        "hotel",
        "pace",
        "transport",
        "budget",
        "meals",
        "other",
    ] | None = None
