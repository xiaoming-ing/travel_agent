<script setup lang="ts">
import { ref } from 'vue'
import type { DailyPlan, Attraction } from '../types'

const props = defineProps<{
  dailyPlans: DailyPlan[]
  allAttractions: Attraction[]
}>()

// 折叠状态：key 是 day 数字，value 是是否展开（默认全部展开）
const openMap = ref<Record<number, boolean>>(
  Object.fromEntries(props.dailyPlans.map((d) => [d.day, true]))
)

function toggle(day: number) {
  openMap.value[day] = !openMap.value[day]
}

// 根据景点名称找到它在全局 attractions 数组里的 index（用于编号徽章）
function findAttractionInfo(name: string): { attraction: Attraction; index: number } | null {
  const idx = props.allAttractions.findIndex((a) => a.name === name)
  if (idx < 0) return null
  return { attraction: props.allAttractions[idx], index: idx }
}

// 根据 day 取出当日景点详情列表（保持 attraction_names 的顺序）
function attractionsOfDay(day: DailyPlan) {
  return day.attraction_names
    .map(findAttractionInfo)
    .filter((x): x is { attraction: Attraction; index: number } => x !== null)
}
</script>

<template>
  <div class="daily-card">
    <div class="card-header">📅 每日行程</div>

    <div class="days">
      <div
        v-for="d in dailyPlans"
        :key="d.day"
        :id="`day-${d.day}`"
        class="day-box"
      >
        <button class="day-head" @click="toggle(d.day)">
          <span class="arrow">{{ openMap[d.day] ? '▾' : '▸' }}</span>
          <span class="day-title">第{{ d.day }}天</span>
          <span class="day-date">{{ d.date }}</span>
        </button>

        <div v-show="openMap[d.day]" class="day-body">
          <!-- 信息框 -->
          <div class="info-box">
            <div><strong>📝 行程描述：</strong>{{ d.description }}</div>
            <div><strong>🚌 交通方式：</strong>{{ d.transport }}</div>
            <div><strong>🏨 住宿：</strong>{{ d.accommodation }}</div>
          </div>

          <!-- 景点安排 -->
          <h4 class="subhead">🎯 景点安排</h4>
          <div class="attractions-grid">
            <div
              v-for="item in attractionsOfDay(d)"
              :key="item.attraction.name"
              class="attraction-card"
            >
              <div v-if="item.attraction.image_url" class="att-image-wrap">
                <img :src="item.attraction.image_url" :alt="item.attraction.name" />
                <span class="att-num">{{ item.index + 1 }}</span>
                <span v-if="item.attraction.ticket_price > 0" class="att-price">
                  ¥{{ item.attraction.ticket_price }}
                </span>
              </div>
              <div class="att-info">
                <div class="att-name">
                  <span v-if="!item.attraction.image_url" class="att-num-inline">
                    {{ item.index + 1 }}
                  </span>
                  {{ item.attraction.name }}
                </div>
                <div class="att-meta"><strong>地址：</strong>{{ item.attraction.address }}</div>
                <div class="att-meta"><strong>游览时长：</strong>{{ item.attraction.duration_minutes }}分钟</div>
                <div class="att-meta"><strong>描述：</strong>{{ item.attraction.description }}</div>
              </div>
            </div>
          </div>

          <!-- 餐饮安排 -->
          <h4 class="subhead">🍽️ 餐饮安排</h4>
          <table class="meals-table">
            <tbody>
              <tr><td class="meal-label">早餐</td><td>{{ d.meals.breakfast }}</td></tr>
              <tr><td class="meal-label">午餐</td><td>{{ d.meals.lunch }}</td></tr>
              <tr><td class="meal-label">晚餐</td><td>{{ d.meals.dinner }}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.daily-card {
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

.days { padding: 16px; display: flex; flex-direction: column; gap: 12px; }

.day-box {
  border: 1px solid #eee;
  border-radius: 10px;
  overflow: hidden;
}
.day-head {
  width: 100%;
  background: #fafafa;
  border: none;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  font-size: 14px;
  text-align: left;
}
.day-head:hover { background: #f0f0f5; }
.arrow { color: #888; }
.day-title { font-weight: 600; color: #333; }
.day-date { margin-left: auto; color: #888; font-size: 13px; }

.day-body { padding: 16px; }

.info-box {
  background: #f7f7fb;
  border-radius: 8px;
  padding: 14px 16px;
  font-size: 13px;
  line-height: 1.8;
  color: #555;
  margin-bottom: 20px;
}
.info-box strong { color: #333; font-weight: 600; }

.subhead {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 20px 0 12px;
}

/* 景点网格 */
.attractions-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.attraction-card {
  border: 1px solid #eee;
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
}
.att-image-wrap {
  position: relative;
  width: 100%;
  height: 180px;
  overflow: hidden;
  background: #f0f0f0;
}
.att-image-wrap img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.att-num {
  position: absolute;
  top: 8px;
  left: 8px;
  width: 30px;
  height: 30px;
  line-height: 30px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  text-align: center;
  font-weight: 700;
  font-size: 14px;
}
.att-price {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 4px 10px;
  border-radius: 12px;
  background: #f56565;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}
.att-num-inline {
  display: inline-block;
  width: 22px;
  height: 22px;
  line-height: 22px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  text-align: center;
  font-size: 12px;
  font-weight: 700;
  margin-right: 8px;
}
.att-info { padding: 12px 14px; font-size: 13px; line-height: 1.7; color: #555; }
.att-name { font-size: 15px; font-weight: 700; color: #222; margin-bottom: 8px; }
.att-meta { margin-bottom: 4px; }
.att-meta strong { color: #666; font-weight: 600; }

/* 餐饮表格 */
.meals-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.meals-table td {
  padding: 10px 14px;
  border-top: 1px solid #eee;
  color: #555;
  line-height: 1.6;
}
.meal-label {
  width: 80px;
  color: #333;
  font-weight: 600;
  background: #fafafa;
}

@media (max-width: 900px) {
  .attractions-grid { grid-template-columns: 1fr; }
}
</style>
