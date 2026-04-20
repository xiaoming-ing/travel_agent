# 结果页前端实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把旅行计划结果渲染成左侧边栏 + 右滚动内容的结果页，替换现有的 JSON 占位。

**Architecture:** 在 `App.vue` 用 `v-if` 切换 FormView / ResultView；结果页按大模块拆成 6 个子组件（OverviewCard / BudgetCard / AttractionMap / DailyPlan / WeatherCard / ResultSidebar），父容器 ResultView 管锚点滚动和 scroll-spy 高亮。

**Tech Stack:** Vue 3 (Composition API, `<script setup>`) + TypeScript + Vite + 高德地图 JS API (`@amap/amap-jsapi-loader`)。

**参考文档:** [设计文档](../specs/2026-04-20-result-view-frontend-design.md)

**测试策略:** 学习项目，不写自动化测试。每个任务完成后在 `npm run dev` 启动的浏览器里手动验证，然后 commit。

**Conventions:**
- 所有 Vue 组件用 `<script setup lang="ts">`，延续现有 FormView 风格
- 颜色变量：紫色渐变 `linear-gradient(135deg, #667eea, #764ba2)`，卡片阴影 `0 4px 20px rgba(0,0,0,0.08)`
- 所有文件路径相对于项目根 `/Users/admin/AI/travel-agent`

---

## 文件清单

**新建：**
- `frontend/.env` — 前端 AMap Key
- `frontend/.env.example` — 提交到 git，示范 Key 格式
- `frontend/src/views/ResultView.vue` — 结果页容器
- `frontend/src/components/ResultSidebar.vue` — 左侧导航
- `frontend/src/components/OverviewCard.vue` — 行程概览卡
- `frontend/src/components/BudgetCard.vue` — 预算卡
- `frontend/src/components/AttractionMap.vue` — 景点地图
- `frontend/src/components/DailyPlan.vue` — 每日行程（含折叠 + 景点/酒店/餐饮）
- `frontend/src/components/WeatherCard.vue` — 天气卡

**修改：**
- `frontend/package.json` — 新增依赖 `@amap/amap-jsapi-loader`
- `frontend/src/App.vue` — 用 ResultView 替换占位 placeholder，调整 body 背景
- `frontend/src/views/FormView.vue` — 根 div 自带紫色渐变背景
- `frontend/src/shims-vue.d.ts` — 可能需要加 `ImportMetaEnv` 类型（Vite 默认已有，不需要额外写）

**验证（无新文件）：**
- `frontend/.gitignore` 无需改（根 `.gitignore` 已有 `.env` 规则，覆盖 frontend/.env）

---

## Task 1: 环境准备（AMap Key、依赖、背景色）

**Files:**
- Create: `frontend/.env`
- Create: `frontend/.env.example`
- Modify: `frontend/package.json` (via npm install)
- Modify: `frontend/src/App.vue` (body 背景色)
- Modify: `frontend/src/views/FormView.vue` (根 div 加紫色渐变背景)

- [ ] **Step 1.1: 创建 `frontend/.env`**

内容：
```
VITE_AMAP_KEY=0d9408e2f9002ded0c9063cce06baf0e
```

- [ ] **Step 1.2: 创建 `frontend/.env.example`**

内容：
```
# 高德 Web 端 JS API Key（注意：不是 Web 服务 Key）
# 申请地址：https://console.amap.com/
VITE_AMAP_KEY=your_amap_js_api_key_here
```

- [ ] **Step 1.3: 安装高德 JS API Loader**

Run:
```bash
cd frontend && npm install @amap/amap-jsapi-loader
```

Expected: `package.json` 的 `dependencies` 多出 `"@amap/amap-jsapi-loader": "^x.x.x"`，`package-lock.json` 更新。

- [ ] **Step 1.4: 修改 `frontend/src/App.vue` 的全局样式**

背景改为浅灰，紫色渐变挪到 FormView 自管。

修改 `<style>` 中 `body` 和 `.app` 部分（文件 40-75 行区域）：

```vue
<style>
/* 全局样式（不加 scoped） */
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, "PingFang SC", sans-serif;
  background: #f5f5f7;
  min-height: 100vh;
  color: #222;
}

.app { min-height: 100vh; }
</style>
```

（删掉原来的 `.placeholder` 那一大段 CSS，我们接下来会换成 ResultView 组件，placeholder 不再需要）

- [ ] **Step 1.5: 修改 `frontend/src/views/FormView.vue`，让根 div 自带紫色渐变背景**

修改 `<style scoped>` 的 `.form-view` 规则（原文件第 157-161 行左右）：

```css
.form-view {
  max-width: 1100px;
  margin: 0 auto;
  padding: 40px 24px 80px;
  min-height: 100vh;
  /* 紫色渐变挪到这里，因为 body 现在是浅灰 */
  background: linear-gradient(135deg, #667eea, #764ba2);
}
```

但这样做会让背景宽度受 `max-width` 限制。更合适的做法是：外层包一个全宽容器，内层保留 max-width 居中。方案 —— 改 template 包一层：

原模板（55 行左右）：
```vue
<template>
  <div class="form-view">
    <!-- ... -->
  </div>
</template>
```

改成：
```vue
<template>
  <div class="form-bg">
    <div class="form-view">
      <!-- ... 原内容不动 -->
    </div>
  </div>
</template>
```

对应 CSS 开头加：
```css
.form-bg {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea, #764ba2);
}
```

`.form-view` 保持原样（不要加 background）。

- [ ] **Step 1.6: 启动 dev server 验证**

Run:
```bash
cd frontend && npm run dev
```

浏览器打开 `http://localhost:5173`（端口以 vite 实际启动为准）。

Expected:
- FormView 页面背景仍是紫色渐变，视觉和之前一致
- 浏览器控制台无报错
- 停止 dev server（Ctrl+C）继续下一步

- [ ] **Step 1.7: 提交**

```bash
git add frontend/.env.example frontend/package.json frontend/package-lock.json frontend/src/App.vue frontend/src/views/FormView.vue
git commit -m "chore(frontend): 环境准备（AMap JS SDK 依赖 + 背景色调整）"
```

（注意：`frontend/.env` 不提交，已被根 `.gitignore` 的 `.env` 规则忽略）

---

## Task 2: ResultView 容器骨架 + 替换 App.vue 占位

目标：建立结果页的容器、顶部按钮、两栏布局骨架，内容区先放静态占位，后面 Task 逐步替换。

**Files:**
- Create: `frontend/src/views/ResultView.vue`
- Modify: `frontend/src/App.vue`

- [ ] **Step 2.1: 创建 `frontend/src/views/ResultView.vue`（骨架）**

```vue
<script setup lang="ts">
import type { TripPlan } from '../types'

defineProps<{ tripPlan: TripPlan }>()
const emit = defineEmits<{ back: [] }>()

function onEditClick() {
  alert('编辑行程 —— 功能开发中')
}
function onExportClick() {
  alert('导出行程 —— 功能开发中')
}
</script>

<template>
  <div class="result-view">
    <!-- 顶部按钮栏 -->
    <header class="top-bar">
      <button class="btn-ghost" @click="emit('back')">← 返回首页</button>
      <div class="top-right">
        <button class="btn-ghost" @click="onEditClick">✏️ 编辑行程</button>
        <button class="btn-ghost" @click="onExportClick">📤 导出行程 ▾</button>
      </div>
    </header>

    <!-- 左侧栏 + 右内容 -->
    <div class="layout">
      <aside class="sidebar-slot">
        <!-- Task 3 会放 ResultSidebar -->
        <div style="padding:16px;background:#fff;border-radius:12px;">侧边栏占位</div>
      </aside>

      <main class="content">
        <section id="overview" class="section-slot">OverviewCard 占位</section>
        <section id="budget" class="section-slot">BudgetCard 占位</section>
        <section id="map" class="section-slot">AttractionMap 占位</section>
        <section id="daily" class="section-slot">DailyPlan 占位</section>
        <section id="weather" class="section-slot">WeatherCard 占位</section>
      </main>
    </div>
  </div>
</template>

<style scoped>
.result-view {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.top-right { display: flex; gap: 8px; }

.btn-ghost {
  padding: 8px 16px;
  border: 1px solid #ddd;
  background: #fff;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  color: #333;
}
.btn-ghost:hover { background: #f5f5f7; }

.layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 20px;
  align-items: start;
}

.sidebar-slot {
  position: sticky;
  top: 24px;
}

.content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.section-slot {
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  min-height: 120px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  color: #888;
}
</style>
```

- [ ] **Step 2.2: 修改 `frontend/src/App.vue`，用 ResultView 替换占位**

替换 `<script setup>` 和 `<template>`（保留 `<style>`）：

```vue
<script setup lang="ts">
import { ref } from 'vue'
import type { TripRequest, TripPlan } from './types'
import { planTrip } from './api'
import FormView from './views/FormView.vue'
import ResultView from './views/ResultView.vue'

const tripPlan = ref<TripPlan | null>(null)
const loading = ref(false)

async function handleSubmit(req: TripRequest) {
  loading.value = true
  try {
    tripPlan.value = await planTrip(req)
  } catch (e: any) {
    alert(`生成失败：${e.message}`)
  } finally {
    loading.value = false
  }
}

function goBack() {
  tripPlan.value = null
}
</script>

<template>
  <div class="app">
    <FormView v-if="!tripPlan" :loading="loading" @submit="handleSubmit" />
    <ResultView v-else :trip-plan="tripPlan" @back="goBack" />
  </div>
</template>
```

`<style>` 保留 Task 1 改过的版本不动。

- [ ] **Step 2.3: 启动 dev server 手动验证**

Run:
```bash
cd frontend && npm run dev
```

步骤：
1. 填表并点"生成旅行计划"（后端需在跑，若没跑起来需先 `cd backend && uvicorn app.main:app --reload`）
2. 等待返回后应看到结果页骨架：顶部按钮 + 左右两栏 + 5 个占位 section
3. 点击"← 返回首页"应回到 FormView
4. 点击"编辑行程"/"导出行程"应弹 alert

Expected: 上述流程完整通过，浏览器控制台无报错。

- [ ] **Step 2.4: 提交**

```bash
git add frontend/src/App.vue frontend/src/views/ResultView.vue
git commit -m "feat(frontend): ResultView 容器骨架 + 替换 App 占位"
```

---

## Task 3: ResultSidebar 组件

**Files:**
- Create: `frontend/src/components/ResultSidebar.vue`
- Modify: `frontend/src/views/ResultView.vue`

- [ ] **Step 3.1: 创建 `frontend/src/components/ResultSidebar.vue`**

```vue
<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  activeId: string
  dailyList: Array<{ day: number; date: string }>
}>()

const emit = defineEmits<{ navigate: [id: string] }>()

// 每日行程子菜单是否展开
const dailyOpen = ref(true)

const mainItems = [
  { id: 'overview', icon: '📋', label: '行程概览' },
  { id: 'budget', icon: '🪙', label: '预算明细' },
  { id: 'map', icon: '📍', label: '景点地图' },
  // 'daily' 单独处理，因为要带展开箭头
  { id: 'weather', icon: '🌤️', label: '天气信息' },
] as const
</script>

<template>
  <nav class="sidebar">
    <!-- 前三项 -->
    <button
      v-for="item in mainItems.slice(0, 3)"
      :key="item.id"
      class="nav-item"
      :class="{ active: activeId === item.id }"
      @click="emit('navigate', item.id)"
    >
      <span class="icon">{{ item.icon }}</span>
      <span>{{ item.label }}</span>
    </button>

    <!-- 每日行程（可展开） -->
    <button
      class="nav-item"
      :class="{ active: activeId === 'daily' || activeId.startsWith('day-') }"
      @click="emit('navigate', 'daily'); dailyOpen = !dailyOpen"
    >
      <span class="icon">📅</span>
      <span>每日行程</span>
      <span class="arrow" :class="{ open: dailyOpen }">▾</span>
    </button>

    <div v-if="dailyOpen" class="sub-items">
      <button
        v-for="d in dailyList"
        :key="d.day"
        class="sub-item"
        :class="{ active: activeId === `day-${d.day}` }"
        @click="emit('navigate', `day-${d.day}`)"
      >
        第{{ d.day }}天
      </button>
    </div>

    <!-- 天气 -->
    <button
      class="nav-item"
      :class="{ active: activeId === 'weather' }"
      @click="emit('navigate', 'weather')"
    >
      <span class="icon">🌤️</span>
      <span>天气信息</span>
    </button>
  </nav>
</template>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: #fff;
  border-radius: 12px;
  padding: 12px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  color: #555;
  text-align: left;
  transition: background 0.15s;
}
.nav-item:hover { background: #f5f5f7; }
.nav-item.active {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
}
.nav-item .icon { font-size: 16px; }
.arrow {
  margin-left: auto;
  transition: transform 0.2s;
  font-size: 12px;
}
.arrow.open { transform: rotate(0deg); }
.arrow:not(.open) { transform: rotate(-90deg); }

.sub-items {
  display: flex;
  flex-direction: column;
  padding-left: 28px;
  gap: 2px;
}
.sub-item {
  padding: 6px 12px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: #777;
  text-align: left;
}
.sub-item:hover { background: #f5f5f7; }
.sub-item.active { background: #e6ecff; color: #4a5fdc; font-weight: 600; }
</style>
```

- [ ] **Step 3.2: 修改 `frontend/src/views/ResultView.vue`，集成 Sidebar**

在 `<script setup>` 加 import 和 activeId ref：

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import type { TripPlan } from '../types'
import ResultSidebar from '../components/ResultSidebar.vue'

const props = defineProps<{ tripPlan: TripPlan }>()
const emit = defineEmits<{ back: [] }>()

// Task 9 会做 scroll-spy，现在先固定为 'overview'
const activeId = ref<string>('overview')

const dailyList = computed(() =>
  props.tripPlan.daily_plans.map((d) => ({ day: d.day, date: d.date }))
)

function onEditClick() {
  alert('编辑行程 —— 功能开发中')
}
function onExportClick() {
  alert('导出行程 —— 功能开发中')
}

function handleNavigate(id: string) {
  // Task 9 会接平滑滚动，现在先只更新 activeId 看高亮切换
  activeId.value = id
}
</script>
```

template 里替换 sidebar-slot 的内容：

```vue
<aside class="sidebar-slot">
  <ResultSidebar
    :active-id="activeId"
    :daily-list="dailyList"
    @navigate="handleNavigate"
  />
</aside>
```

- [ ] **Step 3.3: 启动 dev server 手动验证**

Run:
```bash
cd frontend && npm run dev
```

填表生成到结果页，观察：
1. 左侧边栏正确显示 5 项：行程概览 / 预算明细 / 景点地图 / 每日行程 ▾ / 天气信息
2. "每日行程"下展开显示"第1天" "第2天"等子项
3. 点击不同项，紫色渐变高亮跟随切换
4. 点击"每日行程"本身能切换展开/折叠
5. 点击子项"第1天"，主项保持高亮

Expected: 视觉和参考图一致；点击交互正确。

- [ ] **Step 3.4: 提交**

```bash
git add frontend/src/components/ResultSidebar.vue frontend/src/views/ResultView.vue
git commit -m "feat(frontend): ResultSidebar 侧边栏组件"
```

---

## Task 4: OverviewCard 组件

**Files:**
- Create: `frontend/src/components/OverviewCard.vue`
- Modify: `frontend/src/views/ResultView.vue`

- [ ] **Step 4.1: 创建 `frontend/src/components/OverviewCard.vue`**

```vue
<script setup lang="ts">
defineProps<{
  destination: string
  startDate: string
  endDate: string
  suggestion: string
}>()
</script>

<template>
  <div class="overview-card">
    <div class="card-header">
      <span>📍 {{ destination }}旅行计划</span>
    </div>
    <div class="card-body">
      <div class="row">
        <span class="row-icon">📅</span>
        <div>
          <div class="row-label">日期：</div>
          <div>{{ startDate }} 至 {{ endDate }}</div>
        </div>
      </div>
      <div class="row">
        <span class="row-icon">💡</span>
        <div>
          <div class="row-label">建议：</div>
          <div>{{ suggestion }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overview-card {
  background: #fff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}
.card-header {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  padding: 14px 20px;
  font-size: 16px;
  font-weight: 600;
}
.card-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  font-size: 14px;
  color: #333;
  line-height: 1.6;
}
.row { display: flex; gap: 10px; align-items: flex-start; }
.row-icon { font-size: 16px; margin-top: 2px; }
.row-label { color: #888; margin-bottom: 2px; }
</style>
```

- [ ] **Step 4.2: 修改 `ResultView.vue`，把 OverviewCard 替换 `#overview` 占位**

在 `<script setup>` 顶部加 import：
```ts
import OverviewCard from '../components/OverviewCard.vue'
```

模板里把 `#overview` 那一行改成：
```vue
<section id="overview">
  <OverviewCard
    :destination="tripPlan.destination"
    :start-date="tripPlan.start_date"
    :end-date="tripPlan.end_date"
    :suggestion="tripPlan.suggestion"
  />
</section>
```

（去掉 `class="section-slot"`，因为 OverviewCard 自己有卡片样式）

- [ ] **Step 4.3: 启动 dev server 手动验证**

`npm run dev`，生成结果页。

Expected:
- `#overview` 位置显示紫色头 + 白色卡体
- 标题：📍 上海旅行计划（或其他目的地）
- 日期行：2026-04-21 至 2026-04-24
- 建议行：显示完整的 suggestion 文本

- [ ] **Step 4.4: 提交**

```bash
git add frontend/src/components/OverviewCard.vue frontend/src/views/ResultView.vue
git commit -m "feat(frontend): OverviewCard 行程概览卡"
```

---

## Task 5: BudgetCard 组件

**Files:**
- Create: `frontend/src/components/BudgetCard.vue`
- Modify: `frontend/src/views/ResultView.vue`

- [ ] **Step 5.1: 创建 `frontend/src/components/BudgetCard.vue`**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import type { BudgetBreakdown } from '../types'

const props = defineProps<{ budget: BudgetBreakdown }>()

// 注意 schema 里 BudgetBreakdown 有 total 字段，但后端实际返回的 JSON 里没有 total（只有4个子项）
// 所以这里算总和作为兜底（后端有 total 的话用后端，没有就前端加）
const total = computed(() => {
  const b = props.budget
  return b.total ?? (b.attractions + b.hotel + b.meals + b.transport)
})

const items = computed(() => [
  { icon: '🎟️', label: '景点门票', value: props.budget.attractions },
  { icon: '🏨', label: '酒店住宿', value: props.budget.hotel },
  { icon: '🍽️', label: '餐饮费用', value: props.budget.meals },
  { icon: '🚇', label: '交通费用', value: props.budget.transport },
])
</script>

<template>
  <div class="budget-card">
    <div class="card-header">🪙 预算明细</div>
    <div class="card-body">
      <div class="grid">
        <div v-for="it in items" :key="it.label" class="mini">
          <div class="mini-label">{{ it.icon }} {{ it.label }}</div>
          <div class="mini-value">¥{{ it.value }}</div>
        </div>
      </div>
      <div class="total">
        <span>预估总费用</span>
        <span class="total-value">¥{{ total }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.budget-card {
  background: #fff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}
.card-header {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  padding: 14px 20px;
  font-size: 16px;
  font-weight: 600;
}
.card-body { padding: 20px; }

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}
.mini {
  background: #f7f7fb;
  border-radius: 10px;
  padding: 14px 16px;
  text-align: center;
}
.mini-label { font-size: 13px; color: #777; margin-bottom: 6px; }
.mini-value { font-size: 18px; font-weight: 700; color: #4a5fdc; }

.total {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  border-radius: 10px;
  padding: 14px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 15px;
  font-weight: 600;
}
.total-value { font-size: 22px; }
</style>
```

- [ ] **Step 5.2: 注意类型上的 total 可选**

`frontend/src/types.ts` 里 `BudgetBreakdown.total` 目前是 `number`（必填）。但后端实际 JSON 没返回 total。为了类型和运行时一致，把 `total` 改成可选：

修改 `frontend/src/types.ts` 第 58 行：
```ts
export interface BudgetBreakdown {
  attractions: number
  hotel: number
  meals: number
  transport: number
  total?: number   // 后端可能不返回，前端兜底计算
}
```

- [ ] **Step 5.3: 修改 `ResultView.vue`，集成 BudgetCard**

在 `<script setup>` import：
```ts
import BudgetCard from '../components/BudgetCard.vue'
```

模板 `#budget` 改为：
```vue
<section id="budget">
  <BudgetCard :budget="tripPlan.budget" />
</section>
```

- [ ] **Step 5.4: 启动 dev server 手动验证**

`npm run dev`，查看预算卡：

Expected:
- 紫色头："🪙 预算明细"
- 2×2 小卡：景点门票 ¥320 / 酒店住宿 ¥1600 / 餐饮费用 ¥1200 / 交通费用 ¥200（以实际数据为准）
- 底部紫色渐变总计：¥3320（= 320+1600+1200+200）

- [ ] **Step 5.5: 提交**

```bash
git add frontend/src/components/BudgetCard.vue frontend/src/types.ts frontend/src/views/ResultView.vue
git commit -m "feat(frontend): BudgetCard 预算卡 + BudgetBreakdown.total 改可选"
```

---

## Task 6: AttractionMap 组件（高德地图 + 编号 Marker + 连线）

**Files:**
- Create: `frontend/src/components/AttractionMap.vue`
- Modify: `frontend/src/views/ResultView.vue`

- [ ] **Step 6.1: 创建 `frontend/src/components/AttractionMap.vue`**

```vue
<script setup lang="ts">
import { onMounted, onUnmounted, ref, shallowRef } from 'vue'
import AMapLoader from '@amap/amap-jsapi-loader'
import type { Attraction } from '../types'

const props = defineProps<{ attractions: Attraction[] }>()

const mapContainer = ref<HTMLDivElement | null>(null)
const errorMsg = ref<string | null>(null)
// 用 shallowRef 避免 Vue 深度代理大对象（AMap 地图实例非常大，深度代理会卡）
const mapInstance = shallowRef<any>(null)

onMounted(async () => {
  try {
    const AMap = await AMapLoader.load({
      key: import.meta.env.VITE_AMAP_KEY,
      version: '2.0',
      plugins: ['AMap.Polyline'],
    })

    if (!mapContainer.value) return

    const map = new AMap.Map(mapContainer.value, {
      zoom: 11,
      viewMode: '2D',
    })
    mapInstance.value = map

    // 创建编号 Marker
    const markers = props.attractions.map((a, idx) => {
      const num = idx + 1
      return new AMap.Marker({
        position: [a.longitude, a.latitude],
        content: `<div class="amap-num-marker">${num}</div>`,
        offset: new AMap.Pixel(-14, -14),
        title: a.name,
      })
    })

    // 创建连线（按顺序）
    const polyline = new AMap.Polyline({
      path: props.attractions.map((a) => [a.longitude, a.latitude]),
      strokeColor: '#4a5fdc',
      strokeWeight: 4,
      strokeOpacity: 0.7,
      lineJoin: 'round',
    })

    map.add([...markers, polyline])
    map.setFitView()
  } catch (e: any) {
    errorMsg.value = `地图加载失败：${e.message || '未知错误'}`
    console.error('[AttractionMap]', e)
  }
})

onUnmounted(() => {
  mapInstance.value?.destroy?.()
})
</script>

<template>
  <div class="map-card">
    <div class="card-header">📍 景点地图</div>
    <div class="map-body">
      <div v-if="errorMsg" class="error">{{ errorMsg }}</div>
      <div v-else ref="mapContainer" class="map-container"></div>
    </div>
  </div>
</template>

<!-- 编号 marker 用的样式必须是全局的，不能用 scoped，因为 AMap 在外部 DOM 里渲染 content -->
<style>
.amap-num-marker {
  width: 28px;
  height: 28px;
  line-height: 28px;
  border-radius: 50%;
  background: #4a5fdc;
  color: #fff;
  text-align: center;
  font-weight: 700;
  font-size: 14px;
  border: 2px solid #fff;
  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
}
</style>

<style scoped>
.map-card {
  background: #fff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}
.card-header {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  padding: 14px 20px;
  font-size: 16px;
  font-weight: 600;
}
.map-body {
  padding: 16px;
}
.map-container {
  width: 100%;
  height: 400px;
  border-radius: 8px;
  overflow: hidden;
}
.error {
  padding: 40px;
  text-align: center;
  color: #c33;
  background: #fff5f5;
  border-radius: 8px;
}
</style>
```

- [ ] **Step 6.2: 修改 `ResultView.vue`，集成 AttractionMap**

在 `<script setup>` import：
```ts
import AttractionMap from '../components/AttractionMap.vue'
```

模板 `#map` 改为：
```vue
<section id="map">
  <AttractionMap :attractions="tripPlan.attractions" />
</section>
```

- [ ] **Step 6.3: 启动 dev server 手动验证**

`npm run dev`，生成结果页，滚到 `#map` 位置。

Expected:
- 紫色头 "📍 景点地图"
- 下方显示高德地图，视野自动框住所有景点
- 每个景点是圆形蓝色编号 marker（1, 2, 3...）
- 按顺序有蓝色折线连接所有 marker
- 浏览器控制台无报错

**排查：**
- 如果地图空白：打开 Network 看是否 `webapi.amap.com` 请求返回 401/403 —— 通常是 Key 配错（一定要是"Web端(JS API)"类型）
- 如果报 `INVALID_USER_DOMAIN`：Key 有域名白名单限制；在高德控制台添加 `localhost` 到白名单
- 如果报 `USERKEY_PLAT_NOMATCH`：Key 是 Web 服务类型，不是 JS API 类型，需要重新申请

- [ ] **Step 6.4: 提交**

```bash
git add frontend/src/components/AttractionMap.vue frontend/src/views/ResultView.vue
git commit -m "feat(frontend): AttractionMap 高德地图 + 编号 Marker + 连线"
```

---

## Task 7: DailyPlan 组件（每日折叠 + 景点/酒店/餐饮）

这是最大的一个组件，分几个小步做。

**Files:**
- Create: `frontend/src/components/DailyPlan.vue`
- Modify: `frontend/src/views/ResultView.vue`

- [ ] **Step 7.1: 创建 `frontend/src/components/DailyPlan.vue`（基础结构 + 折叠控制）**

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import type { DailyPlan, Attraction } from '../types'

const props = defineProps<{
  dailyPlans: DailyPlan[]
  allAttractions: Attraction[]
}>()

// 折叠状态：key 是 day 数字，value 是是否展开（默认全部展开）
const openMap = ref<Record<number, boolean>>(
  Object.fromEntries(props.dailyPlans.map((d) => [d.day, true]))
)

function toggle(day: number) {
  openMap.value[day] = !openMap.value[day]
}

// 根据景点名称找到它在全局 attractions 数组里的 index（用于编号徽章）
function findAttractionInfo(name: string): { attraction: Attraction; index: number } | null {
  const idx = props.allAttractions.findIndex((a) => a.name === name)
  if (idx < 0) return null
  return { attraction: props.allAttractions[idx], index: idx }
}

// 根据 day 取出当日景点详情列表（保持 attraction_names 的顺序）
function attractionsOfDay(day: DailyPlan) {
  return day.attraction_names
    .map(findAttractionInfo)
    .filter((x): x is { attraction: Attraction; index: number } => x !== null)
}
</script>

<template>
  <div class="daily-card">
    <div class="card-header">📅 每日行程</div>

    <div class="days">
      <div
        v-for="d in dailyPlans"
        :key="d.day"
        :id="`day-${d.day}`"
        class="day-box"
      >
        <button class="day-head" @click="toggle(d.day)">
          <span class="arrow">{{ openMap[d.day] ? '▾' : '▸' }}</span>
          <span class="day-title">第{{ d.day }}天</span>
          <span class="day-date">{{ d.date }}</span>
        </button>

        <div v-show="openMap[d.day]" class="day-body">
          <!-- 信息框 -->
          <div class="info-box">
            <div><strong>📝 行程描述：</strong>{{ d.description }}</div>
            <div><strong>🚌 交通方式：</strong>{{ d.transport }}</div>
            <div><strong>🏨 住宿：</strong>{{ d.accommodation }}</div>
          </div>

          <!-- 景点安排 -->
          <h4 class="subhead">🎯 景点安排</h4>
          <div class="attractions-grid">
            <div
              v-for="item in attractionsOfDay(d)"
              :key="item.attraction.name"
              class="attraction-card"
            >
              <div v-if="item.attraction.image_url" class="att-image-wrap">
                <img :src="item.attraction.image_url" :alt="item.attraction.name" />
                <span class="att-num">{{ item.index + 1 }}</span>
                <span v-if="item.attraction.ticket_price > 0" class="att-price">
                  ¥{{ item.attraction.ticket_price }}
                </span>
              </div>
              <div class="att-info">
                <div class="att-name">
                  <span v-if="!item.attraction.image_url" class="att-num-inline">
                    {{ item.index + 1 }}
                  </span>
                  {{ item.attraction.name }}
                </div>
                <div class="att-meta"><strong>地址：</strong>{{ item.attraction.address }}</div>
                <div class="att-meta"><strong>游览时长：</strong>{{ item.attraction.duration_minutes }}分钟</div>
                <div class="att-meta"><strong>描述：</strong>{{ item.attraction.description }}</div>
              </div>
            </div>
          </div>

          <!-- 住宿推荐 -->
          <h4 class="subhead">🏩 住宿推荐</h4>
          <div class="hotel-card">
            <div class="hotel-name">{{ d.hotel.name }}</div>
            <div class="hotel-grid">
              <div><strong>地址：</strong>{{ d.hotel.address }}</div>
              <div><strong>类型：</strong>{{ d.hotel.type }}</div>
              <div><strong>价格范围：</strong>{{ d.hotel.price_range }}</div>
              <div><strong>评分：</strong>{{ d.hotel.rating }} ⭐</div>
              <div class="span-2"><strong>距离：</strong>{{ d.hotel.distance_note }}</div>
            </div>
          </div>

          <!-- 餐饮安排 -->
          <h4 class="subhead">🍽️ 餐饮安排</h4>
          <table class="meals-table">
            <tbody>
              <tr><td class="meal-label">早餐</td><td>{{ d.meals.breakfast }}</td></tr>
              <tr><td class="meal-label">午餐</td><td>{{ d.meals.lunch }}</td></tr>
              <tr><td class="meal-label">晚餐</td><td>{{ d.meals.dinner }}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.daily-card {
  background: #fff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}
.card-header {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  padding: 14px 20px;
  font-size: 16px;
  font-weight: 600;
}

.days { padding: 16px; display: flex; flex-direction: column; gap: 12px; }

.day-box {
  border: 1px solid #eee;
  border-radius: 10px;
  overflow: hidden;
}
.day-head {
  width: 100%;
  background: #fafafa;
  border: none;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  font-size: 14px;
  text-align: left;
}
.day-head:hover { background: #f0f0f5; }
.arrow { color: #888; }
.day-title { font-weight: 600; color: #333; }
.day-date { margin-left: auto; color: #888; font-size: 13px; }

.day-body { padding: 16px; }

.info-box {
  background: #f7f7fb;
  border-radius: 8px;
  padding: 14px 16px;
  font-size: 13px;
  line-height: 1.8;
  color: #555;
  margin-bottom: 20px;
}
.info-box strong { color: #333; font-weight: 600; }

.subhead {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 20px 0 12px;
}

/* 景点网格 */
.attractions-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.attraction-card {
  border: 1px solid #eee;
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
}
.att-image-wrap {
  position: relative;
  width: 100%;
  height: 180px;
  overflow: hidden;
  background: #f0f0f0;
}
.att-image-wrap img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.att-num {
  position: absolute;
  top: 8px;
  left: 8px;
  width: 30px;
  height: 30px;
  line-height: 30px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  text-align: center;
  font-weight: 700;
  font-size: 14px;
}
.att-price {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 4px 10px;
  border-radius: 12px;
  background: #f56565;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}
.att-num-inline {
  display: inline-block;
  width: 22px;
  height: 22px;
  line-height: 22px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  text-align: center;
  font-size: 12px;
  font-weight: 700;
  margin-right: 8px;
}
.att-info { padding: 12px 14px; font-size: 13px; line-height: 1.7; color: #555; }
.att-name { font-size: 15px; font-weight: 700; color: #222; margin-bottom: 8px; }
.att-meta { margin-bottom: 4px; }
.att-meta strong { color: #666; font-weight: 600; }

/* 酒店卡片（蓝色渐变） */
.hotel-card {
  background: linear-gradient(135deg, #60a5fa, #93c5fd);
  border-radius: 10px;
  color: #fff;
  padding: 16px 20px;
}
.hotel-name { font-size: 16px; font-weight: 700; margin-bottom: 10px; }
.hotel-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 20px;
  font-size: 13px;
  line-height: 1.7;
}
.hotel-grid strong { font-weight: 600; opacity: 0.9; }
.span-2 { grid-column: span 2; }

/* 餐饮表格 */
.meals-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.meals-table td {
  padding: 10px 14px;
  border-top: 1px solid #eee;
  color: #555;
  line-height: 1.6;
}
.meal-label {
  width: 80px;
  color: #333;
  font-weight: 600;
  background: #fafafa;
}

@media (max-width: 900px) {
  .attractions-grid { grid-template-columns: 1fr; }
  .hotel-grid { grid-template-columns: 1fr; }
  .span-2 { grid-column: span 1; }
}
</style>
```

- [ ] **Step 7.2: 修改 `ResultView.vue`，集成 DailyPlan**

在 `<script setup>` import：
```ts
import DailyPlan from '../components/DailyPlan.vue'
```

模板 `#daily` 改为：
```vue
<section id="daily">
  <DailyPlan
    :daily-plans="tripPlan.daily_plans"
    :all-attractions="tripPlan.attractions"
  />
</section>
```

- [ ] **Step 7.3: 启动 dev server 手动验证**

`npm run dev`，滚到每日行程区域。

Expected（对照样例数据上海 4 天）：
- 紫色头 "📅 每日行程"
- 4 个折叠子卡，默认都展开
- 第 1 天：行程描述 / 交通方式 / 住宿；景点（上海自然博物馆编号①、静安雕塑公园编号②，票价徽章分别 ¥30 和无）；酒店蓝色卡；餐饮三行表格
- 点击"第1天"折叠头能切换展开/折叠，箭头 ▾/▸ 正确切换
- 当景点 image_url 有值时图片正常显示（可能首次加载有延迟）；无 image_url 时图片区隐藏，名称前有紫色小编号
- 酒店卡蓝色渐变，2 列信息布局
- 餐饮三行整齐

**排查：**
- 如果图片 404：说明后端返回的 image_url 暂时失效，这不是前端 bug。可以在浏览器右键图片"在新标签打开"确认
- 如果景点编号错了：检查 `findAttractionInfo` 是否正确用 `tripPlan.attractions` 数组全局索引

- [ ] **Step 7.4: 提交**

```bash
git add frontend/src/components/DailyPlan.vue frontend/src/views/ResultView.vue
git commit -m "feat(frontend): DailyPlan 每日行程组件（折叠 + 景点/酒店/餐饮）"
```

---

## Task 8: WeatherCard 组件

**Files:**
- Create: `frontend/src/components/WeatherCard.vue`
- Modify: `frontend/src/views/ResultView.vue`

- [ ] **Step 8.1: 创建 `frontend/src/components/WeatherCard.vue`**

```vue
<script setup lang="ts">
defineProps<{
  destination: string
  weatherSummary: string
  suggestion: string
}>()
</script>

<template>
  <div class="weather-card">
    <div class="card-header">🌤️ 天气信息</div>
    <div class="card-body">
      <h3 class="title">{{ destination }} 天气摘要</h3>
      <p class="summary">{{ weatherSummary }}</p>
      <div class="callout">
        <div class="callout-head">💡 出行提醒</div>
        <div>{{ suggestion }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.weather-card {
  background: #fff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}
.card-header {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  padding: 14px 20px;
  font-size: 16px;
  font-weight: 600;
}
.card-body { padding: 20px; }
.title { font-size: 16px; color: #333; margin-bottom: 12px; }
.summary { font-size: 14px; line-height: 1.7; color: #555; margin-bottom: 16px; }
.callout {
  background: #fffbe6;
  border-left: 4px solid #f5c518;
  border-radius: 8px;
  padding: 12px 16px;
  font-size: 13px;
  line-height: 1.7;
  color: #555;
}
.callout-head { color: #b58900; font-weight: 600; margin-bottom: 4px; }
</style>
```

- [ ] **Step 8.2: 修改 `ResultView.vue`，集成 WeatherCard**

在 `<script setup>` import：
```ts
import WeatherCard from '../components/WeatherCard.vue'
```

模板 `#weather` 改为：
```vue
<section id="weather">
  <WeatherCard
    :destination="tripPlan.destination"
    :weather-summary="tripPlan.weather_summary"
    :suggestion="tripPlan.suggestion"
  />
</section>
```

- [ ] **Step 8.3: 启动 dev server 手动验证**

`npm run dev`，滚到页面最底部。

Expected:
- 紫色头 "🌤️ 天气信息"
- 标题：{destination} 天气摘要
- 摘要段落正确显示
- 底部黄色 callout "💡 出行提醒" 显示 suggestion

- [ ] **Step 8.4: 提交**

```bash
git add frontend/src/components/WeatherCard.vue frontend/src/views/ResultView.vue
git commit -m "feat(frontend): WeatherCard 天气卡"
```

---

## Task 9: Scroll-spy 高亮跟随 + 点击平滑滚动

到这一步，5 个 section 都已渲染，但 sidebar 高亮是写死的 `'overview'`，点击也不真滚动。这个任务把它们接起来。

**Files:**
- Modify: `frontend/src/views/ResultView.vue`
- Modify: `frontend/src/components/DailyPlan.vue`（可能需要让每天的 `id="day-${day}"` 也被 scroll-spy 监听）

- [ ] **Step 9.1: 修改 `ResultView.vue`，加入 IntersectionObserver**

完整替换 `<script setup>`：

```vue
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import type { TripPlan } from '../types'
import ResultSidebar from '../components/ResultSidebar.vue'
import OverviewCard from '../components/OverviewCard.vue'
import BudgetCard from '../components/BudgetCard.vue'
import AttractionMap from '../components/AttractionMap.vue'
import DailyPlan from '../components/DailyPlan.vue'
import WeatherCard from '../components/WeatherCard.vue'

const props = defineProps<{ tripPlan: TripPlan }>()
const emit = defineEmits<{ back: [] }>()

const activeId = ref<string>('overview')

const dailyList = computed(() =>
  props.tripPlan.daily_plans.map((d) => ({ day: d.day, date: d.date }))
)

function onEditClick() { alert('编辑行程 —— 功能开发中') }
function onExportClick() { alert('导出行程 —— 功能开发中') }

function handleNavigate(id: string) {
  const el = document.getElementById(id)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

// ===== Scroll-spy =====
let observer: IntersectionObserver | null = null

onMounted(async () => {
  // 等 DOM 渲染完，包括 DailyPlan 里的 day-N section
  await nextTick()

  const ids = [
    'overview',
    'budget',
    'map',
    'daily',
    ...props.tripPlan.daily_plans.map((d) => `day-${d.day}`),
    'weather',
  ]

  observer = new IntersectionObserver(
    (entries) => {
      // 找当前页面里可见度最高的 section
      const visible = entries
        .filter((e) => e.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)
      if (visible.length > 0) {
        activeId.value = visible[0].target.id
      }
    },
    {
      // 窗口顶部 20% 以下开始算可见，底部 50% 以下不算
      // 这样滚动到一个 section 顶部就会立刻高亮
      rootMargin: '-20% 0px -50% 0px',
      threshold: [0, 0.1, 0.3, 0.5],
    }
  )

  ids.forEach((id) => {
    const el = document.getElementById(id)
    if (el) observer!.observe(el)
  })
})

onUnmounted(() => {
  observer?.disconnect()
})
</script>
```

模板保持不变（之前已经加好了 import 和各 section）。

- [ ] **Step 9.2: 启动 dev server 手动验证**

`npm run dev`，生成结果页。

Expected:
- **点击跳转**：点击侧边栏"预算明细" → 页面平滑滚动到预算卡位置；点击"每日行程"展开后的"第2天" → 滚动到第 2 天那个 day-box 位置
- **滚动高亮跟随**：手动滚动页面，侧边栏高亮项随之切换：
  - 停在概览卡附近 → "行程概览" 高亮
  - 停在预算卡附近 → "预算明细" 高亮
  - 滚到每日行程第 2 天附近 → "每日行程" + 子项 "第2天" 都高亮
- 浏览器控制台无报错

**排查：**
- 如果高亮不切换：检查 `rootMargin` 设置，可能需要调整数值
- 如果点击跳转没反应：确认 section 上的 id 和传给 `handleNavigate` 的 id 完全一致
- 每天的 day-N section 是在 DailyPlan 内部，`document.getElementById('day-1')` 需要拿到的是 DailyPlan 里的 `<div :id="day-${d.day}">`。scoped CSS 不会影响 id。

- [ ] **Step 9.3: 提交**

```bash
git add frontend/src/views/ResultView.vue
git commit -m "feat(frontend): scroll-spy 高亮跟随 + 点击平滑滚动"
```

---

## Task 10: 联调 + 人工测试清单

这个任务不改代码（或只做 polish 小修），跑一遍完整测试清单，确保端到端没问题。

- [ ] **Step 10.1: 启动前后端**

```bash
# Terminal A
cd backend && uvicorn app.main:app --reload
```

```bash
# Terminal B
cd frontend && npm run dev
```

- [ ] **Step 10.2: 跑完人工测试清单（10 项）**

逐项在浏览器里验证：

1. ☐ 从 FormView 填写表单 → 点"生成" → 等待后跳到 ResultView
2. ☐ 侧边栏 5 项点击跳转：行程概览 / 预算明细 / 景点地图 / 每日行程 / 天气信息 都能平滑滚到对应区域
3. ☐ 手动滚动页面，侧边栏高亮项跟随变化
4. ☐ "每日行程" 点击可展开子菜单（第1天、第2天...），点击子项可跳转到具体某天，且该子项和主项都高亮
5. ☐ 地图正确显示，所有景点有编号蓝圆 marker，按顺序有蓝色连线，视野包含所有景点
6. ☐ 每日行程每个 day-box 可折叠/展开（点击折叠头），箭头 ▾/▸ 正确切换
7. ☐ 景点 `image_url` 为 null（若样例数据里有的话）的卡片不显示图片区，编号显示在名称旁边
8. ☐ 点击"← 返回首页" → 回到 FormView，数据清空，可重新填表
9. ☐ 点击"编辑行程" / "导出行程" → 弹出 alert 占位
10. ☐ 浏览器控制台全程无红色报错

- [ ] **Step 10.3: 如有小问题就地修复**

如果发现样式对不齐、颜色不协调、间距别扭等小问题，就直接调整 CSS，本任务的验证清单通过后才 commit。

如果发现较大问题需要回去改某个组件，记得 commit 时说清楚：

```bash
git commit -m "fix(frontend): [具体问题描述]"
```

- [ ] **Step 10.4: 最终提交**

如果有 polish 修改：
```bash
git add frontend/src
git commit -m "polish(frontend): 结果页联调打磨"
```

如果没改任何代码，就不 commit，直接结束。

---

## 完成标志

- 所有 10 个任务 checkbox 勾完
- 人工测试清单 10 项全部通过
- `git log --oneline` 能看到清晰的提交历史（每个任务至少一个 commit）
