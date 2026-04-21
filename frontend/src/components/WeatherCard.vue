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
