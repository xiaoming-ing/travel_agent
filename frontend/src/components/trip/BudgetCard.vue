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
