"""
Phase2 行程生成器：接收Phase1(ReAct Agent)收集到的原始数据，用structured output 生成最终TripPlan
"""
import langchain
langchain.debug = True
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from app.schemas import Attraction,Hotel,TripPlan,TripRequest
from typing import List
from langchain_core.messages import SystemMessage
import difflib
from app.agents.attraction import search_attraction_by_name, parse_to_attraction


load_dotenv()

llm = ChatDeepSeek(model="deepseek-chat",temperature=0.5)

ITINERARY_PROMPT = """你是一位资深旅行规划师。请基于以下信息，为用户生成一份详细的旅行计划。
【基本信息】
- 目的地：{destination}
- 日期：{start_date}至{end_date}(共{trip_days}天)
- 交通方式：{transport}
- 住宿方式：{accommodation}(参考价格：{hotel_price_range}/晚,用于预算估算)
- 旅行偏好：{preferences}
- 额外要求：{extra}

【天气情况】
{weather}

【候选景点】（必须从下面挑选，不要编造新名字）
{attractions}

【输出要求】
1.suggestion:2-3句整体建议，结合天气说穿衣注意事项：
    **如果【天气情况】显示"暂不可用"，不要编造天气，suggestion里不要给具体温度/降水预测**
2.attractions: 从候选景点挑5-8个填入，补全description(1-2句亮点)、duration_minutes、ticket_price；
    **name 必须和候选列表里的名字完全一致（包括标点、括号、繁简体）——不要简写、不要加注、不要改字**
    longitude/latitude可填0，程序会自动用真实坐标覆盖
3.daily_plans:按天合理分配，每天2-3个景点，不要堆太多；
    attraction_names 里的名字必须和attractions中出现过的完全一致
4.budget: 四项按天数和档次估算总金额（元），hotel按"参考价格*天数"估
5.meals: 每天早/午/晚 具体建议，体现当地特色
6.weather_summary: 基于上面【天气预报】2-3句话总结；
    **如果【天气情况】显示"暂不可用"，此字段输出"天气数据暂未获取，建议出行前通过天气App查询"**
7.hotels:输出空数组[]，程序会自动填充综合打分后的Top3

输出必须是严格的JSON，字段不能遗漏
"""

def _format_attractions(attrs:list[Attraction]) -> str:
    if not attrs:
        return "(无候选)"
    return "\n".join(f"-{a.name}({a.address})" for a in attrs)

def _format_weather(forecast:List[dict]) -> str:
    if not forecast:
        return "(天气数据暂不可用)"
    return "\n".join(
        f"-{f['date']}:白天{f['day_weather']},夜间{f['night_weather']},"
        f"{f['min_temp']}°C~{f['max_temp']}°C,{f['wind']}"
        for f in forecast
    )

def _resolve_coords(
    attr: Attraction,
    raw_attractions: list[Attraction],
    city: str
) -> None:
    """直接在attr上写入真实lng/lat/address/image_url。4级兜底：
    1.完全同名
    2.模糊匹配（80%+相似）
    3.高德POI按名字查
    4.放弃并警告
    """
    name_to_raw = {a.name: a for a in raw_attractions}

    # 1.完全同名
    hit = name_to_raw.get(attr.name)
    if hit:
        attr.longitude = hit.longitude
        attr.latitude = hit.latitude
        attr.address = hit.address
        if not attr.image_url:
            attr.image_url = hit.image_url
        return
    
    # 2.模糊匹配
    matches = difflib.get_close_matches(
        attr.name, # 要去匹配的字符串（比如一个景点名）
        list(name_to_raw.keys()), # 候选字符串列表
        n=1, # 最多返回几个匹配结果
        cutoff=0.8 # 相似度阈值
    )
    if matches:
        hit = name_to_raw[matches[0]]
        print(f"[resolve_coords] 模糊匹配：'{attr.name}' → '{hit.name}'")
        attr.longitude = hit.longitude
        attr.latitude = hit.latitude
        attr.address = hit.address
        if not attr.image_url:
            attr.image_url = hit.image_url
        return
    
    # 3. 高德POI兜底（按LLM输出的名字搜）
    poi = search_attraction_by_name(city, attr.name)
    if poi:
        new_attr = parse_to_attraction(poi)
        if new_attr:
            print(f"[resolve_coords] POI 补全：'{attr.name}' → ({new_attr.longitude}, {new_attr.latitude})")
            attr.longitude = new_attr.longitude
            attr.latitude = new_attr.latitude
            attr.address = new_attr.address
            if not attr.image_url:
                attr.image_url = new_attr.image_url
            return
    
    # 4. 彻底查不到，记录警告
    print(f"[resolve_coords] ⚠️ 无法解析坐标：'{attr.name}'，前端会把它从地图过滤掉")

async def generate_plan(
    request:TripRequest,
    attractions:list[Attraction],
    hotels:list[Hotel],
    weather:list[dict],
) -> dict:
    """Phase2:用Phasse1收集到的原始数据生成完整TripPlan dict。"""
    hotel_price_range = hotels[0].price_range if hotels else "300-500元"

    prompt = ITINERARY_PROMPT.format(
        destination=request.destination,
        start_date=request.start_date,
        end_date=request.end_date,
        trip_days=request.trip_days,
        transport=request.transport,
        accommodation=request.accommodation,
        hotel_price_range=hotel_price_range,
        preferences=",".join(request.preferences) or "无特殊偏好",
        extra=request.extra_requirements or "无",
        weather=_format_weather(weather),
        attractions=_format_attractions(attractions)
    )

    try:
        planner = llm.with_structured_output(TripPlan,include_raw=True) # include_raw=True把模型的原始输出一并返回
        print("[Phase2] 生成行程中...")
        res = await planner.ainvoke([SystemMessage(content=prompt)])
        result: TripPlan | None = res.get('parsed')

        if result is None:
            parsing_error = res.get('parsing_error')
            reason = f"schema 解析异常：{parsing_error}" if parsing_error else "模型未返回结构化输出（tool_calls 为空）"
            raise ValueError(reason)

    except Exception as e:
        print(f"[Phase2] LLM 调用失败：{e}")
        return _fallback_plan(request, reason=f"AI 行程生成失败：{e}")

    print('result:',res)
    ## 后处理 1：景点坐标——4 级兜底，应对 LLM 名字漂移
    for a in result.attractions:
        _resolve_coords(a, attractions, request.destination)
    
    # 后处理 2: 推荐酒店Top3 直接用Phase 1打分结果
    result.hotels = hotels[:3]

    # 后处理3: 天气缺失时强制覆盖，防LLM幻觉
    if not weather:
        result.weather_summary = "⚠️ 天气数据暂未获取，建议出行前通过天气 App 查询"
    return result.model_dump(mode="json")

def _fallback_plan(request: TripRequest, reason: str) -> dict:
    """最小可用降级计划——Phase 1 或 Phase 2 失败时的兜底。"""
    return {
        "destination": request.destination,
        "start_date": str(request.start_date),
        "end_date": str(request.end_date),
        "trip_days": request.trip_days,
        "suggestion": f"⚠️ {reason}",
        "budget": {"attractions": 0, "hotel": 0, "meals": 0, "transport": 0},
        "attractions": [],
        "daily_plans": [],
        "hotels": [],
        "weather_summary": "",
    }