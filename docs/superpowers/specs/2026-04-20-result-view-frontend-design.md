# 结果页前端实现设计

**日期**：2026-04-20
**作者**：xiaoming.hu（与 Claude 协作）
**状态**：已批准，待实现

## 背景

后端 LangGraph 工作流已经跑通，可以返回完整的 `TripPlan` 结构（目的地、日期、预算、景点列表、每日行程、天气摘要）。前端当前状态：

- `FormView.vue` 已完成，用于收集用户需求
- `App.vue` 拿到 `tripPlan` 后只是原样打印 JSON 作为占位
- 需要替换占位，做一个正式的结果展示页

## 设计目标

- 视觉对齐用户提供的参考图：左侧固定侧边栏（5 项锚点）+ 右侧滚动内容区
- 延续 FormView 的风格：白色圆角卡片 + 紫色渐变卡片头
- 组件按大模块拆分（6 个文件），便于学习 Vue props/emit 通信
- 地图用高德 Web 端 JS API 显示景点编号标记 + 连线
- 不做跨页面状态管理：继续用 App.vue 的 `v-if` 切换 FormView/ResultView

## 非目标（YAGNI）

- **编辑行程 / 导出行程 功能**：本次只放占位按钮，点击 `alert('功能开发中')`
- **移动端完整适配**：侧边栏在窄屏下可先隐藏或简化，不做 dropdown 动画
- **跨会话持久化**：刷新页面丢失结果是可以接受的
- **编辑景点/酒店**：不做内联编辑

## 文件结构

```
frontend/
├── .env                         # 新建，放入 VITE_AMAP_KEY，加入 .gitignore
├── .env.example                 # 新建，提交到 git，示范需要配什么
└── src/
    ├── App.vue                  # 修改，用 ResultView 替换占位
    ├── views/
    │   └── ResultView.vue       # 新建
    └── components/
        ├── ResultSidebar.vue    # 新建
        ├── OverviewCard.vue     # 新建
        ├── BudgetCard.vue       # 新建
        ├── AttractionMap.vue    # 新建
        ├── DailyPlan.vue        # 新建
        └── WeatherCard.vue      # 新建
```

## 数据流

```
App.vue (持有 tripPlan: TripPlan | null)
   ↓ props: tripPlan
ResultView.vue (容器，把字段拆给子组件)
   ↓ props（各自需要的字段）
OverviewCard / BudgetCard / AttractionMap / DailyPlan / WeatherCard / ResultSidebar
```

- 所有子组件**只读 props**，不回写数据
- `DailyPlan` 自己管哪几天折叠/展开（局部 ref 数组）
- `ResultSidebar` 自己管"每日行程"子项的展开状态
- `ResultView` 管当前活跃锚点 `activeId`，传给 Sidebar 做高亮
- 返回首页：`ResultView` emit `back` → `App.vue` 清空 `tripPlan`

## 组件细节

### ResultView.vue（容器）

**Props**：`tripPlan: TripPlan`
**Emits**：`back`

**布局**：
- 顶部 bar：`← 返回首页` 左对齐；`编辑行程` `导出行程 ▾` 右对齐
- 主体：CSS grid `grid-template-columns: 220px 1fr`，左 sticky，右滚动
- 右侧内容区依次放 5 个 section，每个带锚点 id：
  - `#overview` → `<OverviewCard>`
  - `#budget` → `<BudgetCard>`
  - `#map` → `<AttractionMap>`
  - `#daily` → `<DailyPlan>`（内部每一天还有子锚点 `#day-1` / `#day-2` / …）
  - `#weather` → `<WeatherCard>`

**Scroll-spy**：
- 在 `onMounted` 里为每个主 section 建一个 `IntersectionObserver`（threshold: 0.3）
- 某个 section 进入可见 30% 时，更新 `activeId`
- `activeId` 作为 prop 传给 `ResultSidebar` 做高亮

**点击跳转**：
- Sidebar emit `navigate(id)` → ResultView 调 `document.getElementById(id)?.scrollIntoView({behavior: 'smooth', block: 'start'})`

**编辑/导出按钮**：点击 `alert('功能开发中')`

### ResultSidebar.vue

**Props**：
- `activeId: string`
- `dailyList: Array<{ day: number; date: string }>`（用于展开子项）

**Emits**：`navigate(id: string)`

**结构**：
- 5 行主导航：行程概览 / 预算明细 / 景点地图 / 每日行程 ▾ / 天气信息
- "每日行程" 右侧 `>`/`v` 箭头，点击切换展开
- 展开后渲染子项："第1天" "第2天" …（点击跳 `day-${day}`）
- 活跃项背景：紫色渐变 + 白字

### OverviewCard.vue

**Props**：`destination, start_date, end_date, suggestion`

**样式**：
- 卡片头：紫色渐变（`linear-gradient(135deg, #667eea, #764ba2)`）+ 白字 `📍 {destination}旅行计划`
- 卡片体：
  - `📅 日期：{start_date} 至 {end_date}`
  - `💡 建议：{suggestion}`

### BudgetCard.vue

**Props**：`budget: BudgetBreakdown`

**布局**：
- 卡片头：紫色渐变 `🪙 预算明细`
- 2×2 小卡（景点门票 / 酒店住宿 / 餐饮费用 / 交通费用）
- 底部一条紫色渐变总计：`预估总费用    ¥{total}`（total 已由后端计算）

### AttractionMap.vue

**Props**：`attractions: Attraction[]`

**加载方式**：`@amap/amap-jsapi-loader` npm 包

```ts
import AMapLoader from '@amap/amap-jsapi-loader'

const AMap = await AMapLoader.load({
  key: import.meta.env.VITE_AMAP_KEY,
  version: '2.0',
  plugins: ['AMap.Polyline'],
})
```

**渲染逻辑**：
- `onMounted` 里创建 `new AMap.Map(containerRef.value, { zoom: 11 })`
- 遍历 `attractions`，为每个景点创建自定义 content 的 `AMap.Marker`，content 是一个蓝色小圆里的编号（数组 index + 1）
- 创建 `AMap.Polyline`，path 是所有景点的 `[lng, lat]` 数组，蓝色
- `map.add([...markers, polyline])`
- `map.setFitView()` 自动调整视野

**卡片头**：紫色渐变 `📍 景点地图`，地图容器高 `400px`

### DailyPlan.vue

**Props**：
- `dailyPlans: DailyPlan[]`
- `allAttractions: Attraction[]`（用来根据 `attraction_names` 查详情）

**结构**：
- 卡片头：紫色渐变 `📅 每日行程`
- 循环渲染每一天，每天是一个子卡片：
  - 锚点 `id="day-{day}"`
  - 折叠头：`▾/▸ 第N天` 左，`{date}` 右。点击切换该天展开状态
  - 展开内容：
    - **灰色信息框**：行程描述 / 交通方式 / 住宿
    - **景点安排**：`grid-template-columns: repeat(2, 1fr)`（窄屏 1 列），每张卡片：
      - 上方：图片（`image_url` 非 null 时），左上角紫色编号徽章（从 `allAttractions` 找到的 index+1），右上角红色票价徽章（`¥{ticket_price}`，为 0 时不显示）
      - `image_url` 为 `null` 时不渲染图片区，紧凑展示
      - 下方：名称（粗体）、地址、游览时长、描述
    - **住宿推荐**：蓝色渐变卡片，显示酒店 name / address / type / price_range / rating（⭐ {rating}）/ distance_note
    - **餐饮安排**：3 行表格（早餐 / 午餐 / 晚餐）

**折叠状态管理**：内部 `ref<Record<number, boolean>>`，默认**全部展开**（用户可以逐天折叠）

### WeatherCard.vue

**Props**：`destination, weather_summary, suggestion`

**结构**：
- 紫色头 `🌤️ 天气信息`
- 正文：`{destination} 天气摘要`（h3）+ `weather_summary` 段落
- 底部 callout 卡：`💡 出行提醒` + `suggestion` 文本，浅黄色背景

## 全局样式

- 页面背景：从原先的紫色渐变改为浅灰 `#f5f5f7`（和参考图一致）。**FormView 保留原紫色渐变背景**，ResultView 用浅灰。
- 卡片：`background: #fff; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08);`
- 卡片头紫色渐变：`linear-gradient(135deg, #667eea, #764ba2)`，白字，padding `16px 20px`

### 背景色切换方式

`body` 的 `background` 不能直接按 ResultView 挂载切换。方案：

- 改 `body` 默认 `background: #f5f5f7`（浅灰）
- `FormView.vue` 的根 div 自己盖一个紫色渐变层（全宽、`min-height: 100vh`）
- 这样 body 底色不需要随路由切换

## AMap 集成细节

**安装**：
```bash
cd frontend && npm install @amap/amap-jsapi-loader
```

**环境变量**：
- `frontend/.env`（加入 `.gitignore`）：
  ```
  VITE_AMAP_KEY=0d9408e2f9002ded0c9063cce06baf0e
  ```
- `frontend/.env.example`（提交到 git）：
  ```
  # 高德 Web 端 JS API Key（不是 Web 服务 Key）
  # 申请地址：https://console.amap.com/
  VITE_AMAP_KEY=your_amap_js_api_key_here
  ```

**TypeScript 类型**：
`@amap/amap-jsapi-loader` 自带类型，但 `AMap.Marker` 等插件对象在用 `AMapLoader.load()` 返回值上是 any，可以用 `as any` 或定义简单的局部类型。不追求严格类型。

## Scroll-spy 实现

**思路**：ResultView 里维护 5 个 section 的 refs，`onMounted` 里为每个建 IntersectionObserver。

```ts
const activeId = ref<string>('overview')
const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting && entry.intersectionRatio >= 0.3) {
        activeId.value = entry.target.id
      }
    })
  },
  { threshold: 0.3 }
)
// 5 个 section 依次 observe
```

**注意事项**：
- 页面刚加载时默认 `activeId = 'overview'`
- 多个 section 同时满足阈值时，用数组里最后一个触发的（先到先得的兜底）
- `onUnmounted` 记得 disconnect observer

## 错误处理

- **AMap 加载失败**（key 无效 / 网络问题）：在地图容器区域显示错误提示 "地图加载失败，请检查 AMap Key 配置"，不阻塞其它区域展示
- **tripPlan 字段缺失**：相信后端 schema 验证，前端不额外校验（信任边界）
- **image_url 404**：浏览器原生行为，可加 `@error` 隐藏图片，作为 polish 项

## 测试策略

- **不写自动化测试**（学习项目，UI 以人工验收为主）
- **人工测试清单**：
  1. 从 FormView 填写表单 → 生成 → 跳到 ResultView，渲染正常
  2. 侧边栏 5 项点击跳转，对应区域平滑滚动到位
  3. 手动滚动页面，侧边栏高亮项跟随变化
  4. "每日行程" 展开后显示子项，点击跳到具体某天
  5. 地图正确显示编号标记和连线，视野包含所有景点
  6. 折叠/展开每一天，内容正确显示
  7. `image_url` 为 null 的景点卡片不显示图片区
  8. 点击 "返回首页" 回到 FormView，数据清空
  9. 点击 "编辑行程" / "导出行程"，alert 占位弹出
  10. 浏览器控制台无报错

## 决策记录

| 问题 | 选择 | 原因 |
|---|---|---|
| 地图方案 | 高德 JS SDK（`@amap/amap-jsapi-loader`） | 后端已用高德，数据有 lng/lat，用户已准备好前端 JS Key |
| 编辑/导出按钮 | 只做占位 | YAGNI，功能值得独立设计 |
| 组件拆分 | 按大模块拆 6 个 | 适合学习 Vue props/emit，文件规模可控 |
| 侧边栏交互 | 点击平滑滚动 + scroll-spy 高亮 | 和参考图一致，体验好 |
| 每日行程子项 | 展开为 "第1天..." 子菜单 | 用户选择，便于跳转 |
| 景点编号 | 按 `attractions` 数组 index + 1 | 地图和景点卡片编号保持一致 |
| 图片为 null | 隐藏图片区 | 视觉更紧凑 |
| 路由方案 | 继续 `v-if` 切换 | 两页面的小应用，省掉 vue-router |
