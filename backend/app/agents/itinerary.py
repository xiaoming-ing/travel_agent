"""
Phase2 行程生成器：接收Phase1(ReAct Agent)收集到的原始数据，用structured output 生成最终TripPlan
"""
import logging
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from app.schemas import Attraction,Hotel,TripPlan,TripRequest
from typing import List
from langchain_core.messages import SystemMessage
import difflib
from app.agents.attraction import search_attraction_by_name, parse_to_attraction
from app.core.tokens import count_tokens
from app.rag.retriever import retrieve_for_attractions

load_dotenv()

logger = logging.getLogger(__name__)

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
    **若某候选景点下方带有【参考资料】，description必须基于参考资料提炼，不得编造与资料矛盾的内容；无【参考资料】的景点，按常识简要生成**
    **name 必须和候选列表里的名字完全一致（包括标点、括号、繁简体）——不要简写、不要加注、不要改字**
    longitude/latitude可填0，程序会自动用真实坐标覆盖；
    **若【额外要求】流露出风格倾向（如"想要小众点，别太商业化""想拍出好看的照片"），挑选时优先呼应这种倾向，并在 description 里体现相应卖点（如人少清静/适合拍照打卡）**
3.daily_plans:按天合理分配，每天2-3个景点，不要堆太多；
    attraction_names 里的名字必须和attractions中出现过的完全一致；
    **若【额外要求】提到体力受限/带老人小孩/想轻松点（如"腿脚不便""带小孩，别太累"），每天减至1-2个景点，且优先候选列表里步行强度低、无需爬山登高的地点**
4.budget: 四项按天数和档次估算总金额（元），hotel按"参考价格*天数"估；
    **若【额外要求】提到预算紧张/想省钱（如"预算有限"），按住宿/餐饮档次的下限估算，并且在 suggestion 中给出省钱建议（如"可优先选择XX，无门票且适合拍照"）**
5.meals: 每天早/午/晚 具体建议，体现当地特色；
    **若【额外要求】提到饮食禁忌/过敏/忌口（如"对海鲜过敏""吃素"),推荐时必须主动避开对应食材，并在描述里简短说明已规避**
6.weather_summary: 基于上面【天气预报】2-3句话总结；
    **如果【天气情况】显示"暂不可用"，此字段输出"天气数据暂未获取，建议出行前通过天气App查询"**
7.hotels:输出空数组[]，程序会自动填充综合打分后的Top3

输出必须是严格的JSON，字段不能遗漏
"""

def _format_attractions(attrs:list[Attraction], knowledge:dict[str,list[str]] | None = None) -> str:
    if not attrs:
        return "(无候选)"
    knowledge = knowledge or {}
    lines = []
    for a in attrs:
        lines.append(f"-{a.name}({a.address})")
        # 若该景点检索到了用户上传的资料，作为【参考资料】附在下面
        hits = knowledge.get(a.name)
        if hits:
            # 多段用分号连起来，截断到200字，避免prompt过长
            material = "；".join(hits)[:200]
            lines.append(f".   【参考资料】{material}")
    return "\n".join(lines)

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
        logger.debug("[resolve_coords] 模糊匹配：'%s' → '%s'", attr.name, hit.name)
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
            logger.debug("[resolve_coords] POI 补全：'%s' → (%s, %s)", attr.name, new_attr.longitude, new_attr.latitude)
            attr.longitude = new_attr.longitude
            attr.latitude = new_attr.latitude
            attr.address = new_attr.address
            if not attr.image_url:
                attr.image_url = new_attr.image_url
            return
    
    # 4. 彻底查不到，记录警告
    logger.warning("[resolve_coords] 无法解析坐标：'%s'，前端会把它从地图过滤掉", attr.name)

async def generate_plan(
    request:TripRequest,
    attractions:list[Attraction],
    hotels:list[Hotel],
    weather:list[dict],
    user_id:str = ""
) -> dict:
    """Phase2:用Phasse1收集到的原始数据生成完整TripPlan dict。"""
    hotel_price_range = hotels[0].price_range if hotels else "300-500元"
    knowledge = await retrieve_for_attractions(
        user_id=user_id,
        city=request.destination,
        names=[a.name for a in attractions]
    )
    if knowledge:
        logger.info("[RAG]%d个景点命中用户资料",len(knowledge))

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
        attractions=_format_attractions(attractions,knowledge)
    )

    try:
        planner = llm.with_structured_output(TripPlan,include_raw=True) # include_raw=True把模型的原始输出一并返回
        logger.info("[Phase2] 生成行程中...")
        res = await planner.ainvoke([SystemMessage(content=prompt)])
        result: TripPlan | None = res.get('parsed')

        if result is None:
            parsing_error = res.get('parsing_error')
            reason = f"schema 解析异常：{parsing_error}" if parsing_error else "模型未返回结构化输出（tool_calls 为空）"
            raise ValueError(reason)

    except Exception as e:
        logger.exception("[Phase2] LLM 调用失败")
        return _fallback_plan(request, reason=f"AI 行程生成失败：{e}"),0

    logger.debug("Phase2 原始输出: %s", res)
    ## 后处理 1：景点坐标——4 级兜底，应对 LLM 名字漂移
    for a in result.attractions:
        _resolve_coords(a, attractions, request.destination)
    
    # 后处理 2: 推荐酒店Top3 直接用Phase 1打分结果
    result.hotels = hotels[:3]

    # 后处理3: 天气缺失时强制覆盖，防LLM幻觉
    if not weather:
        result.weather_summary = "⚠️ 天气数据暂未获取，建议出行前通过天气 App 查询"
    tokens = count_tokens([res["raw"]]) if res.get("raw") is not None else 0
    return result.model_dump(mode="json"), tokens

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