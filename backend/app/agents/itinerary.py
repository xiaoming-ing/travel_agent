"""
行程合成agent。整个workflow的“大脑”

输入：表单+天气总结+候选景点+候选酒店
输出：完整TripPlan(结构化JSON)
"""

from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from app.schemas import Attraction,Hotel,TripPlan
from app.graph.state import TravelState
from langchain_core.messages import SystemMessage
from typing import List

load_dotenv()

# temperature稍高一点，让建议文本不那么模版化；单结构化输出不会因此走形
llm = ChatDeepSeek(model="deepseek-chat",temperature=0.5)

ITINERARY_PROMPT = """你是一位资深旅行规划师。请基于以下信息，为用户生成一份详细的旅行计划。
【基本信息】
- 目的地：{destination}
- 日期： {start_date}至{end_date}(共{trip_days}天)
- 交通方式：{transport}
- 住宿方式：{accommodation}（参考价格：{hotel_price_range}/晚，用于预算估算）
- 旅行偏好：{preferences}
- 额外要求：{extra}

【天气情况】
{weather}

【候选景点】（必须从下面挑选，不要编造新名字）
{attractions}

【输出要求】
1.suggestion: 2-3句整体建议，结合天气说穿衣注意事项；
    **如果【天气情况】显示“暂不可用”，不要编造天气，suggestion里不要给具体温度/降水预测**
2.attractions:从候选景点挑5-8个填入，补全description(1-2句亮点)、duration_minutes、ticket_price;
    longitude/latitude可填0，程序会自动用真实坐标覆盖
3.daily_plans:按天合理分配，每天2-3个景点，不要堆太多；
    attraction_names 里的名字必须和attractions中出现过的完全一致；
    不要包含酒店字段（已从schema移除）
4.budget:四项按天数和档次估算总金额（单位：元），hotel按"参考价格×天数"估
5.meals:每天的早/午/晚餐给具体建议，体现当地特色
6.weather_summary:基于上面【天气预报】用 2-3 句话总结 ——
   整体趋势、温度范围、穿衣和出行提醒（如有降雨/大风要提示）
   **如果【天气情况】显示“暂不可用”，此字段输出“天气数据暂未获取，建议出行前通过天气App查询“**
7.hotels: 请输出空数组 []，程序会自动填充综合打分后的Top3酒店

输出必须是严格的JSON，字段不能遗漏
"""


def _format_attractions(attrs:list[Attraction]) -> str:
    if not attrs:
        return "(无候选，请结合常识推荐改城市知名景点)"
    return "\n".join(f"-{a.name}({a.address})" for a in attrs)

def _format_weather(forecast:List[dict]) -> str:
    if not forecast:
        return "(天气数据暂不可用)"
    return "\n".join(
        f"-{f['date']}:白天{f['day_weather']},夜间{f['night_weather']},"
        f"{f['min_temp']}°C～{f['max_temp']}°C,{f['wind']}"
        for f in forecast
    )

async def itinerary_node(state:TravelState) -> dict:
    req = state["request"]
    weather_raw = state.get("weather_raw", [])
    candidate_attractions = state.get("attractions_raw",[])
    candidate_hotels = state.get("hotels_raw",[])

    # 兜底 1：没有候选景点，直接返回降级计划，不调 LLM
    if not candidate_attractions:
        print("[ItineraryAgent] 无候选景点，返回降级行程")
        return {"trip_plan": _fallback_plan(req, reason="景点数据暂不可用，请稍后重试")}

    # 酒店价格参考：用打分后的Top1价格（若有），否则给兜底
    hotel_price_range = candidate_hotels[0].price_range if candidate_hotels else "300-500元"

    prompt = ITINERARY_PROMPT.format(
        destination=req.destination,
        start_date=req.start_date,
        end_date=req.end_date,
        trip_days=req.trip_days,
        transport=req.transport,
        accommodation=req.accommodation,
        hotel_price_range=hotel_price_range,
        preferences=",".join(req.preferences) or "无特殊偏好",
        extra=req.extra_requirements or "无",
        weather=_format_weather(weather_raw),
        attractions=_format_attractions(candidate_attractions),
    )

    # 关键：with_structured_output强制LLM按TripPlan chema输出
    # 如果输出不合 schema,LanChain会自动重试或报错
    try:  
        planner = llm.with_structured_output(TripPlan)
        print("[ItineraryAgent]生成行程中。。。")
        result: TripPlan = await planner.ainvoke([SystemMessage(content=prompt)])
    except Exception as e:
        print(f"[ItineraryAgent]LLM调用失败：{e}")
        return {"trip_plan":_fallback_plan(req,reason=f"AI 行程生成失败：{e}")}

    # 后处理：用真实数据覆盖LLM可能的幻觉
    # 1。景点坐标/图片以高德真实数据为准 -- LLM编的经纬度是不能用的
    name_to_raw = {a.name:a for a in candidate_attractions}
    for a in result.attractions:
        raw = name_to_raw.get(a.name)
        if raw:
            a.longitude = raw.longitude
            a.latitude = raw.latitude
            a.address = raw.address
            if not a.image_url:
                a.image_url = raw.image_url
    
    # 2.推荐酒店Top3：直接用 hotel_node 综合打分后的前3家
    # LLM不参与酒店选择，避免重复决策 + 幻觉
    result.hotels = candidate_hotels[:3]

    # 3.序列化成dict存回state
    # mode="josn"会把date对象转成“YYYY-MM-DD”字符串，方便前端直接用
    return {"trip_plan":result.model_dump(mode="json")}


def _fallback_plan(req,reason:str) -> dict:
    """生成一个最小可用的降级TripPlan dict,告诉前端'生成失败，请重试'。"""
    return {
        "destination": req.destination,
        "start_date": str(req.start_date),
        "end_date": str(req.end_date),
        "trip_days": req.trip_days,
        "suggestion": f"⚠️ {reason}",
        "budget": {"attractions": 0, "hotel": 0, "meals": 0, "transport": 0},
        "attractions": [],
        "daily_plans": [],
        "hotels": [],
        "weather_summary": "",
    }