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
  { id: 'overview', icon: '📋', label: '行程概览' },
  { id: 'budget', icon: '🪙', label: '预算明细' },
  { id: 'map', icon: '📍', label: '景点地图' },
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
      <span class="icon">{{ item.icon }}</span>
      <span>{{ item.label }}</span>
    </button>

    <!-- 每日行程（可展开） -->
    <button
      class="nav-item"
      :class="{ active: activeId === 'daily' || activeId.startsWith('day-') }"
      @click="emit('navigate', 'daily'); dailyOpen = !dailyOpen"
    >
      <span class="icon">📅</span>
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

    <!-- 天气 -->
    <button
      class="nav-item"
      :class="{ active: activeId === 'weather' }"
      @click="emit('navigate', 'weather')"
    >
      <span class="icon">🌤️</span>
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
  border-radius: 12px;
  padding: 12px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  color: #555;
  text-align: left;
  transition: background 0.15s;
}
.nav-item:hover { background: #f5f5f7; }
.nav-item.active {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
}
.nav-item .icon { font-size: 16px; }
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
  color: #777;
  text-align: left;
}
.sub-item:hover { background: #f5f5f7; }
.sub-item.active { background: #e6ecff; color: #4a5fdc; font-weight: 600; }
</style>
