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
      <span>{{ destination }}行程计划</span>
    </div>
    <div class="card-body">
      <div class="row">
        <span class="row-icon">日期</span>
        <div>
          <div class="row-label">出行时间</div>
          <div>{{ startDate }} 至 {{ endDate }}</div>
        </div>
      </div>
      <div class="row">
        <span class="row-icon">建议</span>
        <div>
          <div class="row-label">规划说明</div>
          <div>{{ suggestion }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overview-card {
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  overflow: hidden;
  box-shadow: var(--shadow-soft);
}
.card-header {
  background: #fff;
  color: var(--color-ink);
  padding: 18px 20px 12px;
  font-size: 22px;
  font-weight: 750;
  border-bottom: 1px solid var(--color-border);
}
.card-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  font-size: 14px;
  color: var(--color-ink);
  line-height: 1.6;
}
.row { display: flex; gap: 10px; align-items: flex-start; }
.row-icon {
  width: 42px;
  flex-shrink: 0;
  border: 1px solid rgba(31, 111, 120, 0.16);
  border-radius: 6px;
  color: var(--color-route);
  background: #edf5f4;
  font-size: 12px;
  font-weight: 750;
  text-align: center;
  padding: 3px 0;
  margin-top: 1px;
}
.row-label { color: var(--color-note); margin-bottom: 2px; font-size: 12px; font-weight: 650; }
</style>
