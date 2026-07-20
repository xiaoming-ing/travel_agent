<script setup lang="ts">
defineProps<{
  destination: string
  weatherSummary: string
  suggestion: string
}>()
</script>

<template>
  <div class="weather-card">
    <div class="card-header">天气信息</div>
    <div class="card-body">
      <h3 class="title">{{ destination }} 天气摘要</h3>
      <p class="summary">{{ weatherSummary }}</p>
      <div class="callout">
        <div class="callout-head">出行提醒</div>
        <div>{{ suggestion }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.weather-card {
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  overflow: hidden;
  box-shadow: var(--shadow-soft);
}
.card-header {
  color: var(--color-ink);
  padding: 16px 20px 12px;
  font-size: 18px;
  font-weight: 750;
  border-bottom: 1px solid var(--color-border);
}
.card-body { padding: 20px; }
.title { font-size: 16px; color: var(--color-ink); margin-bottom: 12px; }
.summary { font-size: 14px; line-height: 1.7; color: var(--color-note); margin-bottom: 16px; }
.callout {
  background: #fbfaf6;
  border-left: 4px solid var(--color-ticket);
  border-radius: 8px;
  padding: 12px 16px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-note);
}
.callout-head { color: var(--color-ink); font-weight: 750; margin-bottom: 4px; }
</style>
