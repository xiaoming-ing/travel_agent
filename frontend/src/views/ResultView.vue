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
        <ResultSidebar
          :active-id="activeId"
          :daily-list="dailyList"
          @navigate="handleNavigate"
        />
      </aside>

      <main class="content">
        <section id="overview">
          <OverviewCard
            :destination="tripPlan.destination"
            :start-date="tripPlan.start_date"
            :end-date="tripPlan.end_date"
            :suggestion="tripPlan.suggestion"
          />
        </section>
        <section id="budget">
          <BudgetCard :budget="tripPlan.budget" />
        </section>
        <section id="map">
          <AttractionMap :attractions="tripPlan.attractions" />
        </section>
        <section id="daily">
          <DailyPlan
            :daily-plans="tripPlan.daily_plans"
            :all-attractions="tripPlan.attractions"
          />
        </section>
        <section id="weather">
          <WeatherCard
            :destination="tripPlan.destination"
            :weather-summary="tripPlan.weather_summary"
            :suggestion="tripPlan.suggestion"
          />
        </section>
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
