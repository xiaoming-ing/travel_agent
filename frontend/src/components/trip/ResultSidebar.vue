<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  activeId: string
  dailyList: Array<{ day: number; date: string }>
}>()

const emit = defineEmits<{ navigate: [id: string] }>()

// 每日行程子菜单是否展开
const dailyOpen = ref(true)

const mainItems = [
  { id: 'overview', label: '行程概览' },
  { id: 'budget', label: '预算明细' },
  { id: 'map', label: '景点地图' },
] as const
</script>

<template>
  <nav class="sidebar">
    <!-- 前三项 -->
    <button
      v-for="item in mainItems"
      :key="item.id"
      class="nav-item"
      :class="{ active: activeId === item.id }"
      @click="emit('navigate', item.id)"
    >
      <span>{{ item.label }}</span>
    </button>

    <!-- 每日行程（可展开） -->
    <button
      class="nav-item"
      :class="{ active: activeId === 'daily' || activeId.startsWith('day-') }"
      @click="emit('navigate', 'daily'); dailyOpen = !dailyOpen"
    >
      <span>每日行程</span>
      <span class="arrow" :class="{ open: dailyOpen }">▾</span>
    </button>

    <div v-if="dailyOpen" class="sub-items">
      <button
        v-for="d in dailyList"
        :key="d.day"
        class="sub-item"
        :class="{ active: activeId === `day-${d.day}` }"
        @click="emit('navigate', `day-${d.day}`)"
      >
        第{{ d.day }}天
      </button>
    </div>

    <!-- 住宿选择 -->
    <button
      class="nav-item"
      :class="{ active: activeId === 'hotels' }"
      @click="emit('navigate', 'hotels')"
    >
      <span>住宿选择</span>
    </button>

    <!-- 天气 -->
    <button
      class="nav-item"
      :class="{ active: activeId === 'weather' }"
      @click="emit('navigate', 'weather')"
    >
      <span>天气信息</span>
    </button>
  </nav>
</template>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  padding: 12px;
  box-shadow: var(--shadow-soft);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  color: var(--color-note);
  text-align: left;
  transition: background 0.15s;
}
.nav-item:hover { background: var(--color-soft); }
.nav-item.active {
  background: #edf5f4;
  color: var(--color-route);
  font-weight: 750;
}
.arrow {
  margin-left: auto;
  transition: transform 0.2s;
  font-size: 12px;
}
.arrow.open { transform: rotate(0deg); }
.arrow:not(.open) { transform: rotate(-90deg); }

.sub-items {
  display: flex;
  flex-direction: column;
  padding-left: 28px;
  gap: 2px;
}
.sub-item {
  padding: 6px 12px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: var(--color-note);
  text-align: left;
}
.sub-item:hover { background: var(--color-soft); }
.sub-item.active { background: #edf5f4; color: var(--color-route); font-weight: 750; }
</style>
