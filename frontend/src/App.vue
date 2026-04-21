<script setup lang="ts">
import { ref } from 'vue'
import type { TripRequest, TripPlan } from './types'
import { planTrip } from './api'
import FormView from './views/FormView.vue'

// 有结果就显示结果页，没有就显示表单页 —— 用 v-if 切换，省掉 vue-router
const tripPlan = ref<TripPlan | null>(null)
const loading = ref(false)

async function handleSubmit(req: TripRequest) {
  loading.value = true
  try {
    tripPlan.value = await planTrip(req)
  } catch (e: any) {
    alert(`生成失败：${e.message}`)
  } finally {
    loading.value = false
  }
}

function goBack() {
  tripPlan.value = null
}
</script>

<template>
  <div class="app">
    <FormView v-if="!tripPlan" :loading="loading" @submit="handleSubmit" />

    <!-- 结果页下一步做，这里先放个临时占位 -->
    <div v-else class="placeholder">
      <button @click="goBack">← 返回首页</button>
      <h2>数据已拿到（结果页下一步实现）</h2>
      <pre>{{ JSON.stringify(tripPlan, null, 2) }}</pre>
    </div>
  </div>
</template>

<style>
/* 全局样式（不加 scoped） */
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, "PingFang SC", sans-serif;
  background: #f5f5f7;
  min-height: 100vh;
  color: #222;
}

.app { min-height: 100vh; }
</style>
