<script setup lang="ts">
import type { TripPlan } from "../../types";
import AttractionMap from "../trip/AttractionMap.vue";
import BudgetCard from "../trip/BudgetCard.vue";
import DailyPlan from "../trip/DailyPlan.vue";
import HotelList from "../trip/HotelList.vue";
import OverviewCard from "../trip/OverviewCard.vue";
import WeatherCard from "../trip/WeatherCard.vue";

defineProps<{
  plan: TripPlan | null;
  isPhase2Timing: boolean;
  phase2FinalMs: number | null;
  phase2ElapsedText: string;
}>();
</script>

<template>
  <main class="preview">
    <div v-if="!plan" class="empty">
      <div class="empty-icon">路线</div>
      <div class="empty-text">
        {{ isPhase2Timing ? "正在整理每日路线..." : "正在收集旅行数据..." }}
      </div>
      <div class="empty-hint">
        <template v-if="isPhase2Timing || phase2FinalMs !== null">
          规划已用时 {{ phase2ElapsedText }}
        </template>
        <template v-else>景点、天气、酒店数据准备中</template>
      </div>
    </div>
    <div v-else class="sections">
      <section>
        <OverviewCard
          :destination="plan.destination"
          :start-date="plan.start_date"
          :end-date="plan.end_date"
          :suggestion="plan.suggestion"
        />
      </section>
      <section><BudgetCard :budget="plan.budget" /></section>
      <section><AttractionMap :attractions="plan.attractions" :hotels="plan.hotels" /></section>
      <section>
        <DailyPlan :daily-plans="plan.daily_plans" :all-attractions="plan.attractions" />
      </section>
      <section><HotelList :hotels="plan.hotels" /></section>
      <section>
        <WeatherCard
          :destination="plan.destination"
          :weather-summary="plan.weather_summary"
          :suggestion="plan.suggestion"
        />
      </section>
    </div>
  </main>
</template>

<style scoped>
.preview { display: flex; flex-direction: column; gap: 20px; }
.empty {
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  padding: 80px 40px;
  text-align: center;
  box-shadow: var(--shadow-soft);
}
.empty-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border: 1px solid rgba(31, 111, 120, 0.2);
  border-radius: 50%;
  color: var(--color-route);
  font-size: 13px;
  font-weight: 750;
  margin-bottom: 16px;
}
.empty-text { color: var(--color-ink); font-size: 15px; margin-bottom: 4px; }
.empty-hint { color: var(--color-muted); font-size: 12px; }
.sections { display: flex; flex-direction: column; gap: 20px; }
</style>
