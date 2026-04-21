<script setup lang="ts">
import { ref } from 'vue'
import type { TripRequest, TripPlan } from './types'
import { planTrip } from './api'
import FormView from './views/FormView.vue'
import ResultView from './views/ResultView.vue'

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
    <ResultView v-else :trip-plan="tripPlan" @back="goBack" />
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
