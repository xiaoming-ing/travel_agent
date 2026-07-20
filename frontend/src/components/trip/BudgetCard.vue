<script setup lang="ts">
import { computed } from 'vue'
import type { BudgetBreakdown } from '../../types'

const props = defineProps<{ budget: BudgetBreakdown }>()

// 后端实际返回的 JSON 里可能没有 total，这里算总和作为兜底
const total = computed(() => {
  const b = props.budget
  return b.total ?? (b.attractions + b.hotel + b.meals + b.transport)
})

const items = computed(() => [
  { code: '票', label: '景点门票', value: props.budget.attractions },
  { code: '住', label: '酒店住宿', value: props.budget.hotel },
  { code: '餐', label: '餐饮费用', value: props.budget.meals },
  { code: '行', label: '交通费用', value: props.budget.transport },
])
</script>

<template>
  <div class="budget-card">
    <div class="card-header">预算明细</div>
    <div class="card-body">
      <div class="grid">
        <div v-for="it in items" :key="it.label" class="mini">
          <div class="mini-label"><span>{{ it.code }}</span>{{ it.label }}</div>
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

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}
.mini {
  background: #fbfaf6;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 14px 16px;
}
.mini-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--color-note);
  margin-bottom: 8px;
}
.mini-label span {
  width: 22px;
  height: 22px;
  line-height: 22px;
  text-align: center;
  border-radius: 6px;
  background: #edf5f4;
  color: var(--color-route);
  font-weight: 750;
}
.mini-value { font-size: 20px; font-weight: 750; color: var(--color-ink); }

.total {
  background: var(--color-ink);
  color: #fff;
  border-radius: 8px;
  padding: 14px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 15px;
  font-weight: 650;
}
.total-value { font-size: 22px; }

@media (max-width: 640px) {
  .grid { grid-template-columns: 1fr; }
}
</style>
