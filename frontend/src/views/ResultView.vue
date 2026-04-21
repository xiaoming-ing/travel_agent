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
