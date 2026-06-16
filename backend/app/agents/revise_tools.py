"""
工具 = 确定性的修改操作（无LLM调用）
Agent = 解析用户反馈 -> 决定调用哪个工具 -> 传精确参数
"""
import logging
from langchain_core.tools import tool
from app.agents.hotel import (
    compute_centroid,
    fetch_hotels_around,
    parse_to_hotel,
    haversine,
    score_hotel
)
from langchain_deepseek import ChatDeepSeek
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage, HumanMessage
from app.schemas import Attraction,Hotel
import copy
from app.agents.attraction import search_attraction_by_name, parse_to_attraction
import contextvars

logger = logging.getLogger(__name__)


# 当前修改操作的上下文，工具读写它（Agent执行过程中的共享内存）
"""
_CTX = {
    "plan":当前行程（可修改）
    "raw_attractions":候选景点
    "raw_hotels":候选酒店
    "transport":出行方式
}
因为tool不能直接拿到函数参数，只能读全局
"""
_ctx_var: contextvars.ContextVar[dict] = contextvars.ContextVar('revise_ctx',default=None)

def reset_ctx() -> None:
    _ctx_var.set({})

def get_ctx() -> dict:
    val = _ctx_var.get()
    if val is None:
        reset_ctx()
        return _ctx_var.get()  
    return val
@tool
def replace_day_attractions(day: int, new_attraction_names: list[str]) -> str:
    """把指定一天的景点整组替换为新名字列表。
    名字可以是【候选景点】里的，也可以是用户指定的新景点——
    不在候选库的名字程序会自动查高德 POI 补全信息，查不到才报错。
    不能和其他天已安排的景点重复。

    Args:
        day: 第几天，从 1 开始
        new_attraction_names: 2-3 个景点名字
    """
    plan = get_ctx()["plan"]
    city = plan.get("destination", "")

    if day < 1 or day > len(plan["daily_plans"]):
        return f"day={day} 超出范围（行程共 {len(plan['daily_plans'])} 天）"

    all_names = {a.name for a in get_ctx()["raw_attractions"]}
    auto_added: list[str] = []

    # === 处理不在候选库的名字：查 POI 自动补全 ===
    # 注意：POI 返回的官方名可能跟用户输入不一致（"长城" → "八达岭长城"），
    # 要把列表里的用户写法替换为 POI 真实名，不然后续按名字找不到
    resolved_names: list[str] = []
    for name in new_attraction_names:
        if name in all_names:
            resolved_names.append(name)
            continue

        poi = search_attraction_by_name(city, name)
        if not poi:
            return f"景点 {name!r} 在高德 POI 里没找到。名字可能不准确，请换个说法。"
        new_attr = parse_to_attraction(poi)
        if not new_attr:
            return f"景点 {name!r} 数据解析失败"

        real_name = new_attr.name
        # 加进 raw_attractions（以后改别的天也能看到）
        get_ctx()["raw_attractions"].append(new_attr)
        all_names.add(real_name)
        # 同步到 trip_plan.attractions，前端地图/卡片才能渲染
        existing = {a["name"] for a in plan["attractions"]}
        if real_name not in existing:
            plan["attractions"].append(new_attr.model_dump(mode="json"))
        auto_added.append(real_name)
        resolved_names.append(real_name)

    # === 校验：不能和其他天重复 ===
    used_in_other_days: set[str] = set()
    for i, dp in enumerate(plan["daily_plans"]):
        if i != day - 1:
            used_in_other_days.update(dp["attraction_names"])
    duplicates = [n for n in resolved_names if n in used_in_other_days]
    if duplicates:
        return (
            f"这些景点已在其他天安排：{duplicates}，会重复。"
            f"请换别的，或先明确要不要从其他天移除。"
        )

    plan["daily_plans"][day - 1]["attraction_names"] = resolved_names
    get_ctx()["plan"] = plan

    msg = f"Day {day} 景点已更新为：{', '.join(resolved_names)}"
    if auto_added:
        msg += f"（新加到候选库：{', '.join(auto_added)}）"
    return msg


@tool
def change_hotel_type(new_type:str) -> str:
    """更换推荐酒店的档次，会按新档次重新搜索并按交通方式综合打分。
    
    Args:
        new_type: 必须是"经济型酒店"/"舒适型酒店"/"豪华型酒店"/"民宿" 之一
    """

    valid = {"经济型酒店", "舒适型酒店", "豪华型酒店", "民宿"}
    if new_type not in valid:
        return f"new_type 必须是{valid}之一"
    
    raw_attractions = get_ctx()["raw_attractions"]
    if not raw_attractions:
        return "无候选景点，无法计算酒店中心"
    
    centroid = compute_centroid(raw_attractions)
    if centroid is None:
        return "景点坐标无效"
    
    pois = fetch_hotels_around(centroid,new_type,limit=15)
    hotels = [h for h in (parse_to_hotel(p,new_type) for p in pois) if h]

    cx,cy = centroid
    scored = []
    transport = get_ctx().get("transport","公共交通")
    for h in hotels:
        d = haversine(h.latitude, h.longitude, cy, cx)
        h.distance_note = f"距景点中心 {d:.1f}km"
        scored.append((score_hotel(h.rating, d, transport), h))
    scored.sort(key=lambda x:x[0],reverse=True)
    top3 = [h for _,h in scored[:3]]

    get_ctx()["plan"]["hotels"] = [h.model_dump(mode="json") for h in top3]
    return f"酒店已改为 {new_type}，Top3：{', '.join(h.name for h in top3)}"

REVISE_TOOLS = [replace_day_attractions,change_hotel_type]

_revise_llm = ChatDeepSeek(model="deepseek-chat",temperature=0.2)
revise_agent = create_agent(_revise_llm,tools=REVISE_TOOLS)

REVISE_SYSTEM_PROMPT_TEMPLATE = """你是旅行行程修改助手。解析用户反馈，调用合适的工具修改行程。
====当前行程摘要====
{plan_summary}

====可用候选景点（replace_day_attractions只能用这些）====
{candidates}

可用工具：
- replace_day_attractions(day, new_attraction_names): 换某天的景点
    * 优先从【已收集的候选景点】里挑
    * 用户明确指定的新景点也可以（例如"八达岭长城"），程序会自动从高德 POI 查询补全
- change_hotel_type(new_type): 换酒店档次（"经济型酒店"/"舒适型酒店"/"豪华型酒店"/"民宿"）

规则：
- 一次调用一个工具就够了
- 从用户反馈里提取精确参数（day是数字，不是第二天）
- 同一景点不能出现在多天里（避免重复）
- 调完工具直接回复"修改完成",不要再自己描述行程
"""


def _summarize_plan(plan:dict) -> str:
    lines = [f"目的地{plan['destination']}，共{plan['trip_days']}天"]
    for dp in plan["daily_plans"]:
        lines.append(f"- Day {dp['day']}({dp['date']}):{','.join(dp['attraction_names'])}")
    if plan.get("hotels"):
        lines.append(f"酒店 Top3：{', '.join(h['name'] for h in plan['hotels'])}")
    return "\n".join(lines)

async def apply_revision(
    feedback:str,
    current_plan:dict,
    raw_attractions:list[Attraction],
    raw_hotels:list[Hotel],
    transport:str,
) -> dict:
    """运行迷你ReAct agent,把feedback转成对current_plan的修改"""
    reset_ctx()
    get_ctx()["plan"] = copy.deepcopy(current_plan)
    get_ctx()["raw_attractions"] = raw_attractions
    get_ctx()["raw_hotels"] = raw_hotels
    get_ctx()["transport"] = transport

    candidates_str = "\n".join(f"-{a.name}" for a in raw_attractions)
    sys_msg = REVISE_SYSTEM_PROMPT_TEMPLATE.format(
        plan_summary=_summarize_plan(current_plan),
        candidates=candidates_str
    )

    logger.info("[Revise] 用户反馈：%s", feedback)

    try:
        await revise_agent.ainvoke(
            {"messages":[
                SystemMessage(content=sys_msg),
                HumanMessage(content=f"用户反馈:{feedback}")
            ]},
            config={"recursion_limit":5}
        )
    except Exception as e:
        logger.exception("[Revise] 修改失败")
        # 修改失败就返回原行程，不中断对话
        return current_plan
    
    return get_ctx()["plan"]