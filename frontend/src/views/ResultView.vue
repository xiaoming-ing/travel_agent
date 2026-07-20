<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import type { TripPlan } from '../types'
import ResultSidebar from '../components/trip/ResultSidebar.vue'
import OverviewCard from '../components/trip/OverviewCard.vue'
import BudgetCard from '../components/trip/BudgetCard.vue'
import AttractionMap from '../components/trip/AttractionMap.vue'
import DailyPlan from '../components/trip/DailyPlan.vue'
import HotelList from '../components/trip/HotelList.vue'
import WeatherCard from '../components/trip/WeatherCard.vue'

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
    'hotels',
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
      <button class="btn-ghost" @click="emit('back')">返回对话调整</button>
      <div class="top-right">
        <button class="btn-ghost" @click="onEditClick">编辑行程</button>
        <button class="btn-ghost" @click="onExportClick">导出行程</button>
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
          <AttractionMap :attractions="tripPlan.attractions" :hotels="tripPlan.hotels"/>
        </section>
        <section id="daily">
          <DailyPlan
            :daily-plans="tripPlan.daily_plans"
            :all-attractions="tripPlan.attractions"
          />
        </section>
        <section id="hotels">
          <HotelList :hotels="tripPlan.hotels" />
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
  padding: 28px;
}

.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
}
.top-right { display: flex; gap: 8px; }

.btn-ghost {
  padding: 8px 14px;
  border: 1px solid var(--color-border);
  background: #fff;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  color: var(--color-ink);
}
.btn-ghost:hover { background: var(--color-soft); border-color: #d8d0c2; }

.layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 18px;
  align-items: start;
}

.sidebar-slot {
  position: sticky;
  top: 24px;
}

.content {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.section-slot {
  background: #fff;
  border-radius: var(--radius-card);
  padding: 24px;
  min-height: 120px;
  border: 1px solid var(--color-border);
  color: var(--color-muted);
}

@media (max-width: 900px) {
  .result-view { padding: 18px 14px; }
  .top-bar { align-items: flex-start; gap: 10px; flex-direction: column; }
  .layout { grid-template-columns: 1fr; }
  .sidebar-slot { position: static; }
}
</style>
