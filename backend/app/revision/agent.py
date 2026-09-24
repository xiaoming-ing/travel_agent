"""把自然语言反馈转换为确定性的行程修订工具调用。"""

import copy
import logging

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_deepseek import ChatDeepSeek

from app.core.tokens import count_tokens
from app.revision.context import get_ctx, reset_ctx
from app.revision.tools import REVISE_TOOLS
from app.schemas import Attraction, Hotel, TravelIntent

logger = logging.getLogger(__name__)

load_dotenv()

_revise_llm = ChatDeepSeek(model="deepseek-chat", temperature=0.2)
revise_agent = create_agent(_revise_llm, tools=REVISE_TOOLS)

REVISE_SYSTEM_PROMPT_TEMPLATE = """你是旅行行程修改助手。解析用户反馈，调用合适的工具修改行程。
====当前行程摘要====
{plan_summary}

====已收集到候选景点（优先从这里挑选，但不限于这些）====
{candidates}

====必须继续遵守的结构化旅行意图====
{intent}

可用工具：
- replace_day_attractions(day, new_attraction_names): 换某天的景点
    *new_attraction_names 必须是【具体景点名】,不能是抽象类别
    * 优先从上面的候选景点挑
    * 候选里没有合适的，你可以根据常识给出该城市真实存在的具体景点名，程序自动去高德POI查询补全（查不到才失败）
- change_hotel_type(new_type): 换酒店档次（"经济型酒店"/"舒适型酒店"/"豪华型酒店"/"民宿"）
- add_attraction(day, attraction_name): 向某天增加一个具体景点
- remove_attraction(day, attraction_name): 从某天删除一个景点
- change_day_pace(day, max_attractions): 把某天缩减为最多 1 或 2 个景点
- change_transport(new_transport, day): 修改全部或某天的交通方式
- update_meal_constraints(restrictions): 更新忌口和饮食限制
- update_budget_limit(new_limit): 更新全程总预算上限

【关键】用户常说模糊需求，你要把它翻译成具体景点名再调用工具：
- "换成室内活动"->想成该城市的室内去处，如博物馆/美术馆/科技馆/商场，
    给出具体名字（例如南京 ->["南京博物院","德基美术馆"])
- "太累了" / "太赶" / "轻松点" -> 这是【减负】信号，必须做两件事：
    1.减少景点数量（参考上面行程摘要里当天现有几个，改后要【更少】，
    比如原本2个减到1个，原本3个减到2个，绝不能变多)；
    2.保留/替换成轻松的（离得近、室内、步行少）
    例：某天原本 ["红山森林动物园", "玄武湖景区"] → 说太累 → ["玄武湖景区"]（只留1个轻松的）
- "公园太多了"->减少自然景点的数量，不是等量替换
- "换成户外"-> 换成公园/景区等户外具体景点
- 用户没说第几天时，结合行程摘要推断最合适的一天

规则：
- 一次调用一个工具就够了
- 从用户反馈里提取精确参数（day是数字，不是第二天）
- 必须真正调用工具来修改，不要只用文字回复说"已修改"
- 同一景点不能出现在多天里（避免重复）
- 调完工具直接回复"修改完成",不要再自己描述行程
"""


def _summarize_plan(plan: dict) -> str:
    lines = [f"目的地{plan['destination']}，共{plan['trip_days']}天"]
    for daily in plan["daily_plans"]:
        lines.append(
            f"- Day {daily['day']}({daily['date']}):{','.join(daily['attraction_names'])}"
        )
    if plan.get("hotels"):
        lines.append(f"酒店 Top3：{', '.join(hotel['name'] for hotel in plan['hotels'])}")
    return "\n".join(lines)


async def apply_revision(
    feedback: str,
    current_plan: dict,
    raw_attractions: list[Attraction],
    raw_hotels: list[Hotel],
    transport: str,
    intent: TravelIntent | None = None,
) -> tuple[dict, int, str | None]:
    """运行修订 agent，把反馈转换为对 current_plan 的修改。"""
    reset_ctx()
    get_ctx()["plan"] = copy.deepcopy(current_plan)
    get_ctx()["raw_attractions"] = raw_attractions
    get_ctx()["raw_hotels"] = raw_hotels
    get_ctx()["transport"] = transport
    get_ctx()["intent"] = intent or TravelIntent()

    candidates = "\n".join(f"-{attraction.name}" for attraction in raw_attractions)
    system_message = REVISE_SYSTEM_PROMPT_TEMPLATE.format(
        plan_summary=_summarize_plan(current_plan),
        candidates=candidates,
        intent=get_ctx()["intent"].model_dump_json(indent=2),
    )
    logger.info("[Revise] 用户反馈：%s", feedback)

    try:
        result = await revise_agent.ainvoke(
            {
                "messages": [
                    SystemMessage(content=system_message),
                    HumanMessage(content=f"用户反馈:{feedback}"),
                ]
            },
            config={"recursion_limit": 5},
        )
    except Exception:
        logger.exception("[Revise] 修改失败")
        return get_ctx()["plan"], 0, "修改服务暂时不可用，请稍后重试"

    tokens = count_tokens(result.get("messages", []))
    new_plan = get_ctx()["plan"]
    messages = result.get("messages", [])
    changed = new_plan != current_plan
    if changed:
        note = None
    else:
        tool_messages = [
            message for message in messages if isinstance(message, ToolMessage)
        ]
        if tool_messages:
            note = f"没能修改成功：{tool_messages[-1].content}"
        else:
            note = "我不太确定你想怎么改,能说得更具体点吗?比如「把第 2 天换成南京博物院」。"

    logger.info("[Revise] changed=%s,note=%s", changed, note)
    return new_plan, tokens, note
