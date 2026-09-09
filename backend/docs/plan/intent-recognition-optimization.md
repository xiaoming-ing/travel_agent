# 用户额外要求与意图识别优化方案

## 1. 背景

当前系统允许用户在 `TripRequest.extra_requirements` 中输入最多 1000 字的自由文本，例如：

> 带老人，想去夫子庙，不爬山，预算控制在 3000 元，不吃海鲜。

现有实现没有独立的结构化意图识别层，而是在两个阶段分别依赖大模型理解原文：

1. 数据收集 Agent 判断是否需要查询具体地点或地点类型。
2. 行程生成模型再次理解风格、体力、预算、忌口等要求。
3. 行程生成后的用户反馈，由修改 Agent 使用另一套 Prompt 重新判断。

这种方式可以覆盖常见 Demo 场景，但存在重复理解、结果不一致、难以追踪、关键约束无法确定性校验等问题。

## 2. 优化目标

- 用户的额外要求只做一次结构化解析，各阶段共享解析结果。
- 区分硬约束和软偏好，避免“尽量满足”和“必须满足”混在一起。
- 支持必去、避开、行程节奏、同行人、无障碍、预算、忌口等常见意图。
- 只在关键信息冲突或无法继续规划时追问用户。
- 行程生成后，对可验证的关键约束执行确定性校验。
- 用户多轮修改时保留最初的约束，避免修改后破坏预算、忌口等要求。
- 模型或外部服务失败时，保留现有降级能力。

## 3. 目标流程

```text
用户提交 TripRequest
        ↓
intent_node：结构化意图识别
        ↓
TravelIntent
        ↓
是否存在关键歧义或冲突
   ├─ 有：interrupt 追问 → 合并用户回答
   └─ 无
        ↓
Phase 1：按结构化意图收集景点、天气、酒店数据
        ↓
Phase 2：基于候选数据和结构化意图生成行程
        ↓
约束校验
   ├─ 通过：展示行程
   └─ 未通过：确定性修正或让模型定向修正一次
        ↓
用户反馈 → 反馈分类 → 更新 TravelIntent → 调用修改工具
```

现有 LangGraph 和两阶段规划架构继续保留，采用渐进式改造，不整体推翻重写。

## 4. 数据模型设计

新增 `app/schemas/intent.py`，定义结构化意图模型：

```python
from typing import Literal

from pydantic import BaseModel, Field


class TravelIntent(BaseModel):
    must_visit: list[str] = Field(default_factory=list)
    avoid_places: list[str] = Field(default_factory=list)

    themes: list[str] = Field(default_factory=list)
    pace: Literal["relaxed", "normal", "packed"] = "normal"
    activity_environment: Literal["indoor", "outdoor", "mixed"] = "mixed"

    traveler_types: list[
        Literal["elderly", "child", "infant", "couple", "solo"]
    ] = Field(default_factory=list)
    accessibility_needs: list[str] = Field(default_factory=list)

    dietary_restrictions: list[str] = Field(default_factory=list)

    budget_limit: int | None = None
    budget_level: Literal["economy", "normal", "premium"] | None = None

    hotel_requirements: list[str] = Field(default_factory=list)
    time_requirements: list[str] = Field(default_factory=list)
    excluded_activities: list[str] = Field(default_factory=list)
    special_requests: list[str] = Field(default_factory=list)

    ambiguities: list[str] = Field(default_factory=list)
```

示例解析结果：

```json
{
  "must_visit": ["夫子庙"],
  "avoid_places": [],
  "themes": [],
  "pace": "relaxed",
  "activity_environment": "mixed",
  "traveler_types": ["elderly"],
  "accessibility_needs": ["减少步行", "避免登高"],
  "dietary_restrictions": ["海鲜"],
  "budget_limit": 3000,
  "budget_level": null,
  "hotel_requirements": [],
  "time_requirements": [],
  "excluded_activities": ["爬山"],
  "special_requests": [],
  "ambiguities": []
}
```

`extra_requirements` 原文继续保留，用于审计、兼容和补充表达细节；业务逻辑优先使用 `TravelIntent`。

## 5. 意图识别规则

新增 `app/agents/intent.py`，使用低温度模型和结构化输出生成 `TravelIntent`。

输入包括：

- 目的地、日期、交通、住宿等标准表单字段。
- 用户选择的标准旅行偏好。
- `extra_requirements` 原文。
- 已保存的用户长期偏好（如果存在）。

识别原则：

- 不补充用户没有表达过的硬约束。
- “一定要去”“必须安排”归入 `must_visit`。
- “不要去”“避开”“不想去”归入 `avoid_places` 或 `excluded_activities`。
- “最好”“偏向”“想要”通常作为软偏好处理。
- 明确金额转换为 `budget_limit`；无法判断是总预算还是日预算时加入 `ambiguities`。
- “老人”“腿脚不便”“轮椅”等同时影响同行人、节奏和无障碍要求。
- 解析不确定但不影响规划的信息放入 `special_requests`，不擅自扩大含义。

## 6. 对话图改造

修改 `app/graph/conversation.py`，在状态中加入：

```python
class ConversationState(TypedDict):
    request: TripRequest
    intent: TravelIntent
    trip_plan: Optional[dict]
    raw_attractions: list[Attraction]
    raw_hotels: list[Hotel]
    last_feedback: Optional[str]
    token_used: int
    revise_note: Optional[str]
```

节点顺序调整为：

```text
START → intent → clarify → plan → feedback
```

### 6.1 intent_node

- 解析标准表单和额外要求。
- 输出 `TravelIntent`。
- 模型调用失败时生成默认意图，并保留原始 `extra_requirements` 供现有 Prompt 使用。

### 6.2 clarify_node

除现有日期和偏好检查外，增加关键冲突检查：

- 同一个地点同时出现在必去和避开列表。
- 预算金额含义不明确，且会显著影响规划。
- 无障碍要求与指定活动明显冲突。
- 多个要求互相排斥，无法生成可用行程。

非关键歧义不追问，使用安全、保守的默认值继续规划。

### 6.3 修复偏好追问校验

当前偏好追问答案按逗号切分后直接通过 `model_copy(update=...)` 写回，可能绕开 `Preference` 枚举校验。

改造时需要：

- 将回答映射到允许的标准偏好。
- 无法映射的内容进入 `TravelIntent.themes` 或 `special_requests`。
- 重新执行 Pydantic 校验，禁止未校验数据直接写入 `TripRequest.preferences`。

## 7. Phase 1 数据收集改造

修改 `app/graph/workflow.py`：

```python
async def run_workflow(
    request: TripRequest,
    intent: TravelIntent,
    config: RunnableConfig | None = None,
    user_id: str = "",
) -> dict:
    ...
```

执行策略：

- `must_visit` 中的地点逐个执行具体地点查询并加入候选。
- `themes` 与标准 `preferences` 合并后映射为 POI 类型或检索关键词。
- 室内、户外、亲子、轻松游等意图影响候选数据的检索范围。
- `avoid_places` 在候选返回后执行确定性过滤。
- 多个必去地点不能因为 Agent 调用次数限制被静默遗漏。
- 酒店附加条件第一版仍交给规划模型；后续可继续扩展酒店查询参数。

第一版保留现有 ReAct Agent，但向其传递结构化意图。后续可根据日志评估，逐步将固定工具调用改为普通程序编排，以减少不确定性和模型调用成本。

## 8. Phase 2 行程生成改造

修改 `app/agents/itinerary.py`，将 Prompt 中的用户要求拆分为：

```text
硬约束：
- 必须安排：夫子庙
- 禁止安排：爬山类活动
- 饮食禁止：海鲜
- 总预算上限：3000 元

软偏好：
- 行程节奏：轻松
- 同行人：老人
- 优先减少步行和登高
```

要求：

- 硬约束必须满足。
- 软偏好在候选数据允许时尽量满足。
- 原始自由文本作为不可信用户内容单独传入，不能覆盖系统规则或结构化约束。
- 保留现有天气缺失保护、候选景点名称限制和坐标补全逻辑。

## 9. 结果约束校验

新增 `app/agents/plan_validator.py`：

```python
class ValidationResult(BaseModel):
    passed: bool
    violations: list[str] = Field(default_factory=list)
```

第一版校验项：

- 所有 `must_visit` 都出现在每日行程中。
- `avoid_places` 没有出现在最终行程中。
- 同一景点没有跨天重复。
- 每日景点名称存在于 `TripPlan.attractions`。
- `relaxed` 模式每天最多安排 1～2 个景点。
- 明确禁止的活动没有被安排。
- 预算总额没有超过 `budget_limit`。
- 行程日期、天数和 Day 序号一致。

处理策略：

1. 可由程序安全修正的问题直接修正，例如删除重复景点。
2. 需要重新规划的问题，将具体违规项交给生成模型定向修正一次。
3. 第二次仍不满足时保留可用部分，并明确返回未满足项，禁止无限重试。

饮食忌口可以通过 Prompt 和关键词检查加强，但不能把推荐结果描述为食品安全保证。实际餐厅的配料、后厨交叉污染等仍需用户自行确认。

## 10. 用户反馈与修改能力

### 10.1 反馈路由

将当前精确完成词表升级为“规则优先、模型兜底”。

新增结构：

```python
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
```

路由规则：

- “挺好的”“就这样”“按这个来”“不用改了”识别为结束。
- “可以，但第二天轻松一点”识别为修改，不能因为包含“可以”而结束。
- 单纯询问信息进入问答分支，不应误改行程。
- 无法确认时向用户追问，不执行猜测性修改。

### 10.2 修改工具

在现有工具基础上增加：

- `add_attraction`
- `remove_attraction`
- `replace_day_attractions`
- `change_hotel_type`
- `change_day_pace`
- `change_transport`
- `update_meal_constraints`
- `update_budget_limit`

所有反馈先更新 `TravelIntent`，再修改行程。每轮修改完成后重新执行约束校验，确保原始预算、忌口、必去和无障碍要求不会丢失。

## 11. 失败与降级策略

- 意图识别失败：使用默认 `TravelIntent`，继续沿用原始文本 Prompt。
- 外部地点查询失败：保留当前候选数据，并明确提示未找到的必去地点。
- 行程生成失败：继续使用现有 `_fallback_plan` 最小可用降级计划。
- 约束修正失败：返回可用行程和未满足项，不宣称已经完全满足。
- 修改 Agent 没有调用工具或工具失败：保持原计划不变，向用户说明具体原因。

## 12. 测试计划

### 12.1 意图识别

- “带老人，不爬山”解析为轻松节奏和无障碍要求。
- “预算控制在 3000”进入预算字段。
- “不吃海鲜，但想吃当地特色”同时保留正向偏好和负向约束。
- “一定去夫子庙，不去总统府”正确提取必去和避开地点。
- 没有表达过的要求不会被模型补充为硬约束。

### 12.2 冲突追问

- 同一地点同时必去和避开时触发追问。
- “预算 3000”含义无法判断且影响规划时触发追问。
- 非关键表达不触发多余追问。

### 12.3 数据收集与生成

- 多个必去地点全部进入候选集合。
- 避开地点不会进入最终行程。
- 必去地点漏排时触发一次自动修正。
- 轻松模式每天最多安排 1～2 个景点。
- 总预算不超过用户明确设置的上限。

### 12.4 多轮反馈

- “挺好的，就这样”结束会话。
- “可以，但第二天太赶了”进入修改流程。
- “把第二天删掉一个景点”可以执行单点删除。
- 修改酒店后仍保留预算和同行人约束。
- 修改景点后仍保留忌口和无障碍要求。

### 12.5 降级路径

- 意图模型不可用时不阻断首次生成。
- 地图服务查询失败时返回明确说明。
- 修改失败时原计划不发生变化。
- 定向修正最多执行一次，不出现无限循环。

## 13. 实施阶段与时间

### 阶段一：意图模型和对话接入，约 3～4 小时

- 新增 `TravelIntent`。
- 新增意图识别 Agent 和 `intent_node`。
- 将意图加入 LangGraph 状态。
- 修复偏好追问绕过枚举校验的问题。
- 增加基础意图单元测试。

### 阶段二：生成链路和约束校验，约 3～4 小时

- Phase 1 使用结构化意图收集候选数据。
- Phase 2 使用硬约束和软偏好生成行程。
- 新增基础结果校验器。
- 对可修复问题增加一次定向修正。

### 阶段三：多轮修改，约 3～5 小时

- 改造完成/修改/问答路由。
- 增加常用修改工具。
- 修改反馈同步更新 `TravelIntent`。
- 每轮修改后重新执行约束校验。

### 阶段四：回归和稳定性验证，约 2～3 小时

- 补充典型、冲突、多意图和失败场景测试。
- 调整意图识别 Prompt。
- 验证模型和第三方服务失败时的降级路径。
- 检查 token 使用和整体响应耗时。

预计总工期为 1.5～2 个工作日。第一天完成首次行程的结构化意图闭环，第二天完成多轮修改、测试和稳定性处理。

## 14. 文件改动清单

预计新增：

- `app/schemas/intent.py`
- `app/agents/intent.py`
- `app/agents/plan_validator.py`
- `tests/test_intent.py`
- `tests/test_plan_validator.py`

预计修改：

- `app/schemas/__init__.py`
- `app/graph/conversation.py`
- `app/graph/workflow.py`
- `app/agents/itinerary.py`
- `app/agents/revise_tools.py`
- `tests/test_conversation.py`
- `tests/test_workflow.py`
- `tests/test_revise_tools.py`

## 15. 验收标准

- 典型额外要求的结构化识别准确率达到约 90%。
- 必去和明确避开条件拥有确定性校验。
- 预算、节奏、同行人、忌口可以跨修改轮次保留。
- 常见满意表达不会误入修改流程。
- 含“可以”但仍提出修改的反馈不会提前结束会话。
- 无法识别的关键要求不会静默忽略，而是追问或明确提示。
- 模型或外部地图服务失败时仍可走现有降级路径。
- 所有现有测试通过，并新增意图识别、约束校验和反馈路由测试。

## 16. 暂不纳入本次范围

- 自动预订酒店、门票或餐厅。
- 对餐饮过敏安全作真实性保证。
- 重写现有地图、天气和酒店数据源。
- 将整个 ReAct 数据收集流程一次性改成纯程序编排。
- 建设完整的线上意图标注与训练平台。

这些内容可在本轮结构化意图数据积累后，根据真实使用数据继续规划。
