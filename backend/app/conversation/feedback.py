import logging
from typing import Optional

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_deepseek import ChatDeepSeek
from langgraph.graph import END

from app.schemas import FeedbackIntent

logger = logging.getLogger(__name__)

load_dotenv()

feedback_llm = ChatDeepSeek(model="deepseek-chat", temperature=0.6)
feedback_classifier_llm = ChatDeepSeek(model="deepseek-chat", temperature=0)


def classify_feedback_by_rule(feedback: str) -> FeedbackIntent | None:
    normalized = feedback.strip().lower()
    if not normalized:
        return FeedbackIntent(action="unknown")

    explicit_finish_phrases = ("挺好的", "就这样", "按这个来", "不用改了")
    contrast_markers = ("但", "不过", "但是", "还要", "还得", "需要", "请")
    if (
        any(phrase in normalized for phrase in explicit_finish_phrases)
        and not any(marker in normalized for marker in contrast_markers)
    ):
        return FeedbackIntent(action="finish")

    revision_markers = {
        "但", "改", "修改", "调整", "换", "删", "增加", "添加", "取消",
        "轻松点", "太赶", "太累", "不要", "不吃", "降低", "提高", "改成",
    }
    if any(marker in normalized for marker in revision_markers):
        revision_type = "other"
        if any(marker in normalized for marker in ("景点", "换", "删", "增加", "添加")):
            revision_type = "attractions"
        elif "酒店" in normalized:
            revision_type = "hotel"
        elif any(marker in normalized for marker in ("轻松", "太赶", "太累", "节奏")):
            revision_type = "pace"
        elif "交通" in normalized:
            revision_type = "transport"
        elif "预算" in normalized:
            revision_type = "budget"
        elif any(marker in normalized for marker in ("餐", "吃", "忌口")):
            revision_type = "meals"
        return FeedbackIntent(action="revise", revision_type=revision_type)

    finish_phrases = {"满意", "ok", "可以", "没问题", "完成", "done", "结束", "好"}
    if normalized in finish_phrases:
        return FeedbackIntent(action="finish")

    if any(marker in normalized for marker in ("?", "？", "吗", "么", "什么", "为什么", "怎么", "是否")):
        return FeedbackIntent(action="question")
    return None


async def classify_feedback(feedback: str) -> FeedbackIntent:
    ruled = classify_feedback_by_rule(feedback)
    if ruled is not None:
        return ruled

    classifier = feedback_classifier_llm.with_structured_output(FeedbackIntent)
    try:
        return await classifier.ainvoke(
            [
                SystemMessage(content=(
                    "判断用户对旅行计划的反馈类型。包含任何修改要求时必须选择 revise；"
                    "只表达满意时选择 finish；只询问信息时选择 question；无法判断选 unknown。"
                )),
                HumanMessage(content=feedback),
            ]
        )
    except Exception:
        logger.exception("[Feedback] 分类失败")
        return FeedbackIntent(action="unknown")


def summarize_plan_for_feedback(plan: Optional[dict]) -> str:
    if not plan:
        return "暂无行程"

    lines = [
        f"目的地：{plan.get('destination', '')}",
        f"天数：{plan.get('trip_days', '')}",
    ]
    for daily in plan.get("daily_plans", []):
        attractions = "、".join(daily.get("attraction_names", []))
        lines.append(f"Day {daily.get('day')}：{attractions}")
    hotels = plan.get("hotels") or []
    if hotels:
        lines.append(f"酒店：{'、'.join(hotel.get('name', '') for hotel in hotels[:3])}")
    return "\n".join(lines)


def fallback_feedback_question(last_feedback: Optional[str]) -> str:
    feedback = (last_feedback or "").strip()
    if feedback:
        return "我按你的反馈调了一版，你看看现在顺不顺。还有哪里别扭，直接说。"
    return "我先把行程排好了，你看看右侧预览。哪里不顺直接说，我再改。"


async def build_feedback_question(
    last_feedback: Optional[str],
    trip_plan: Optional[dict],
) -> str:
    feedback = (last_feedback or "").strip()
    plan_summary = summarize_plan_for_feedback(trip_plan)
    logger.info("[Feedback] LLM 看到的真实行程:\n%s", plan_summary)
    system_prompt = (
        "你是旅行规划产品里的中文对话助手。"
        "根据用户上一轮反馈，生成一句自然的确认，告诉用户可以看右侧预览。"
        "要求：口语化，不要模板腔；不要说'行程已生成'；"
        "【严禁提及任何具体景点名或地名】——去了哪由右侧预览展示，你只做概括性确认；"
        "不要列举例子；"
    )
    user_prompt = (
        f"用户上一轮反馈：{feedback or '无，这是首次生成行程'}\n\n"
        f"当前行程摘要：\n{plan_summary}\n\n"
        "请直接输出要展示给用户的话。"
    )
    try:
        response = await feedback_llm.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )
    except Exception:
        logger.exception("[Feedback] 生成反馈提示失败")
        return fallback_feedback_question(last_feedback)
    content = (getattr(response, "content", "") or "").strip()
    return content or fallback_feedback_question(last_feedback)


def should_revise(state: dict) -> str:
    feedback = (state.get("last_feedback") or "").strip().lower()
    done_words = {"满意", "ok", "可以", "没问题", "完成", "done", "结束", "好"}
    return END if feedback in done_words else "revise"
