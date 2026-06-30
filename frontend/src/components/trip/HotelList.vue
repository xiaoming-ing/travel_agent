<script setup lang="ts">
import type { Hotel } from '../../types'

defineProps<{ hotels: Hotel[] }>()

function stars(rating: number): string {
  const full = Math.round(rating)
  return '⭐'.repeat(full) + '☆'.repeat(Math.max(0, 5 - full))
}
</script>

<template>
  <div class="hotels-card">
    <div class="card-header">🏨 住宿选择</div>

    <div v-if="hotels.length === 0" class="empty">
      暂无推荐酒店
    </div>

    <div v-else class="hotel-list">
      <div
        v-for="(h, idx) in hotels"
        :key="h.name"
        class="hotel-item"
        :class="{ top: idx === 0 }"
      >
        <div class="rank">NO.{{ idx + 1 }}</div>
        <div class="body">
          <div class="name-row">
            <span class="name">{{ h.name }}</span>
            <span class="type">{{ h.type }}</span>
          </div>
          <div class="meta-grid">
            <div><strong>地址：</strong>{{ h.address }}</div>
            <div><strong>价格：</strong>{{ h.price_range }}</div>
            <div>
              <strong>评分：</strong>
              <span class="stars">{{ stars(h.rating) }}</span>
              <span class="rating-num">{{ h.rating }}</span>
            </div>
            <div><strong>距离：</strong>{{ h.distance_note || '—' }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hotels-card {
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
.empty {
  padding: 40px 20px;
  text-align: center;
  color: #999;
  font-size: 14px;
}

.hotel-list {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.hotel-item {
  display: flex;
  gap: 16px;
  align-items: stretch;
  border: 1px solid #eee;
  border-radius: 10px;
  padding: 14px 16px;
  background: #fff;
  transition: box-shadow 0.15s;
}
.hotel-item:hover { box-shadow: 0 2px 10px rgba(0,0,0,0.06); }
.hotel-item.top {
  border-color: transparent;
  background: linear-gradient(135deg, #eef0ff, #f5edff);
}

.rank {
  flex-shrink: 0;
  width: 56px;
  font-size: 14px;
  font-weight: 700;
  color: #4a5fdc;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e0e4ff;
}
.hotel-item.top .rank {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  border-color: transparent;
}

.body { flex: 1; min-width: 0; }

.name-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 10px;
}
.name {
  font-size: 16px;
  font-weight: 700;
  color: #222;
}
.type {
  font-size: 12px;
  color: #667eea;
  background: #eef0ff;
  padding: 2px 8px;
  border-radius: 10px;
}

.meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px 20px;
  font-size: 13px;
  line-height: 1.7;
  color: #555;
}
.meta-grid strong { color: #333; font-weight: 600; }
.stars { letter-spacing: 1px; margin-right: 4px; }
.rating-num { color: #f59e0b; font-weight: 600; }

@media (max-width: 900px) {
  .meta-grid { grid-template-columns: 1fr; }
}
</style>
