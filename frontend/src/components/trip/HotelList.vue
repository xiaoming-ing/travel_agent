<script setup lang="ts">
import type { Hotel } from '../../types'

defineProps<{ hotels: Hotel[] }>()

</script>

<template>
  <div class="hotels-card">
    <div class="card-header">住宿选择</div>

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
.empty {
  padding: 40px 20px;
  text-align: center;
  color: var(--color-muted);
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
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 14px 16px;
  background: #fff;
  transition: box-shadow 0.15s;
}
.hotel-item:hover { background: #fbfaf6; }
.hotel-item.top {
  border-color: rgba(31, 111, 120, 0.28);
  background: #edf5f4;
}

.rank {
  flex-shrink: 0;
  width: 56px;
  font-size: 14px;
  font-weight: 750;
  color: var(--color-route);
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border-radius: 8px;
  border: 1px solid rgba(31, 111, 120, 0.16);
}
.hotel-item.top .rank {
  background: var(--color-route);
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
  font-weight: 750;
  color: var(--color-ink);
}
.type {
  font-size: 12px;
  color: var(--color-route);
  background: #edf5f4;
  padding: 2px 8px;
  border-radius: 10px;
}

.meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px 20px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-note);
}
.meta-grid strong { color: var(--color-ink); font-weight: 650; }
.rating-num { color: var(--color-signal); font-weight: 750; }

@media (max-width: 900px) {
  .meta-grid { grid-template-columns: 1fr; }
}
</style>
