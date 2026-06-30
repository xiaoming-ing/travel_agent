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
