<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { TripRequest } from '../types'
import { getPreferences } from '../api/index'

// ===== 父子通信 =====
// props: 父组件告诉我们是否正在提交（按钮 disable）
// emit: 用户点"生成" → 把表单数据抛给父组件处理
const props = defineProps<{
  loading?: boolean
}>()
const emit = defineEmits<{
  'submit-chat': [req: TripRequest]
}>()

// ===== 表单字段 =====
// ref 让每个字段都是响应式的，改变会自动触发视图更新
const destination = ref('')
const startDate = ref('')
const endDate = ref('')
const transport = ref('公共交通')
const accommodation = ref('经济型酒店')
const preferences = ref<string[]>(['自然风光'])    // 多选：字符串数组
const extraRequirements = ref('')

// ===== 下拉选项（和后端约定一致）=====
const TRANSPORTS = ['公共交通', '自驾', '打车', '步行']
const ACCOMMODATIONS = ['经济型酒店', '舒适型酒店', '豪华型酒店', '民宿']
const PREFERENCE_OPTIONS = [
  { key: '历史文化', icon: '🏛️' },
  { key: '自然风光', icon: '🏞️' },
  { key: '美食', icon: '🍜' },
  { key: '购物', icon: '🛍️' },
  { key: '艺术', icon: '🎨' },
  { key: '休闲', icon: '☕' },
  { key: '亲子', icon: '👶' },

]

// ===== 自动计算旅行天数 =====
// computed 会根据依赖的 ref 变化自动重算，比手动 watch 省事
const tripDays = computed(() => {
  if (!startDate.value || !endDate.value) return 0
  const s = new Date(startDate.value)
  const e = new Date(endDate.value)
  const diff = Math.round((e.getTime() - s.getTime()) / 86400000)
  return diff >= 0 ? diff + 1 : 0  // 含头尾
})

// ===== 按钮可点条件 =====
const canSubmit = computed(() =>
  destination.value &&
  startDate.value &&
  endDate.value &&
  tripDays.value > 0
)

function handleSubmitChat() {
  if (!canSubmit.value || props.loading) return   // 防抖:提交中不响应重复点击
  emit('submit-chat', buildRequest())
}

function buildRequest(): TripRequest {
  return {
    destination: destination.value,
    start_date: startDate.value,
    end_date: endDate.value,
    transport: transport.value,
    accommodation: accommodation.value,
    preferences: preferences.value,
    extra_requirements: extraRequirements.value.trim() || null,
  }
}

onMounted(async () => {
  const saved = await getPreferences()
  if (!saved) return
  if (saved.transport) transport.value = saved.transport
  if (saved.accommodation) accommodation.value = saved.accommodation
  if (saved.preferences && saved.preferences.length) {
    preferences.value = saved.preferences
  }
})
</script>

<template>
  <div class="form-bg">
    <div class="form-view">
      <header class="hero">
        <p class="eyebrow">Trip planning desk</p>
        <h1>把目的地整理成可执行行程</h1>
        <p>输入时间、偏好和约束，系统会按景点、天气、酒店和路线生成一份可继续调整的计划。</p>
      </header>

    <!-- ========== 目的地与日期 ========== -->
    <section class="card">
      <h2>目的地与日期</h2>
      <div class="grid">
        <div class="field">
          <label><span class="req">*</span> 目的地城市</label>
          <input type="text" v-model="destination" placeholder="请输入城市，如：成都" />
        </div>

        <div class="field">
          <label><span class="req">*</span> 开始日期</label>
          <input type="date" v-model="startDate" />
        </div>

        <div class="field">
          <label><span class="req">*</span> 结束日期</label>
          <!-- :min 绑定 startDate，防止结束日期早于开始 -->
          <input type="date" v-model="endDate" :min="startDate" />
        </div>

        <div class="field">
          <label>旅行天数</label>
          <div class="days-badge">{{ tripDays }}天</div>
        </div>
      </div>
    </section>

    <!-- ========== 偏好设置 ========== -->
    <section class="card">
      <h2>偏好设置</h2>
      <div class="grid">
        <div class="field">
          <label>交通方式</label>
          <select v-model="transport">
            <option v-for="t in TRANSPORTS" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>

        <div class="field">
          <label>住宿偏好</label>
          <select v-model="accommodation">
            <option v-for="a in ACCOMMODATIONS" :key="a" :value="a">{{ a }}</option>
          </select>
        </div>

        <div class="field wide">
          <label>旅行偏好（多选）</label>
          <div class="checkboxes">
            <!-- v-model 绑数组，勾选自动 push/splice -->
            <label v-for="p in PREFERENCE_OPTIONS" :key="p.key" class="checkbox">
              <input type="checkbox" :value="p.key" v-model="preferences" />
              <span>{{ p.key }}</span>
            </label>
          </div>
        </div>
      </div>
    </section>

    <!-- ========== 额外要求 ========== -->
    <section class="card">
      <h2>额外要求</h2>
      <textarea
        v-model="extraRequirements"
        rows="4"
        placeholder="请输入您的额外要求，例如：想去看升旗、需要无障碍设施、对海鲜过敏等..."
      ></textarea>
    </section>

      <!-- ========== 生成按钮 ========== -->
      <div class="submit-row">
        <button class="submit primary" :disabled="!canSubmit || props.loading" @click="handleSubmitChat">
          {{ props.loading ? '正在启动...' : '开始规划' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* scoped 让样式只作用于本组件，不会污染全局 */
.form-bg {
  min-height: 100vh;
  background:
    linear-gradient(180deg, rgba(255,255,255,0.56), rgba(255,255,255,0) 340px),
    var(--color-paper);
}

.form-view {
  max-width: 1120px;
  margin: 0 auto;
  padding: 48px 28px 80px;
}

.hero {
  max-width: 760px;
  color: var(--color-ink);
  margin-bottom: 28px;
  border-left: 4px solid var(--color-signal);
  padding-left: 20px;
}
.eyebrow {
  color: var(--color-route);
  font-size: 12px;
  font-weight: 750;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.hero h1 {
  font-size: 34px;
  line-height: 1.18;
  margin-bottom: 10px;
  letter-spacing: 0;
}
.hero p {
  color: var(--color-note);
  line-height: 1.7;
  font-size: 15px;
}

.card {
  background: rgba(255,255,255,0.86);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  padding: 22px 24px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-soft);
}
.card h2 {
  font-size: 17px;
  margin-bottom: 18px;
  color: var(--color-ink);
  font-weight: 750;
}

.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}
.field.wide { grid-column: span 4; }

.field label {
  display: block;
  font-size: 12px;
  color: var(--color-note);
  margin-bottom: 8px;
  font-weight: 600;
}
.req { color: var(--color-signal); margin-right: 4px; }

.field select,
.field input[type="date"],
.field input[type="text"],
textarea {
  width: 100%;
  padding: 11px 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  background: #fff;
  font-family: inherit;
  color: var(--color-ink);
}
.field select:focus,
.field input:focus,
textarea:focus {
  border-color: var(--color-route);
  box-shadow: 0 0 0 3px rgba(31, 111, 120, 0.12);
}

.days-badge {
  padding: 11px 12px;
  border-radius: 8px;
  background: #edf5f4;
  color: var(--color-route);
  text-align: center;
  font-weight: 750;
  border: 1px solid rgba(31, 111, 120, 0.16);
}

.checkboxes {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
}
.checkbox {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  cursor: pointer;
  color: var(--color-note);
  margin-bottom: 0;  /* 覆盖 label 的默认 margin */
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 9px 10px;
  background: #fff;
}
.checkbox input { cursor: pointer; }

textarea {
  resize: vertical;
  min-height: 80px;
}

.submit {
  width: 100%;
  padding: 14px 16px;
  background: var(--color-signal);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 750;
  cursor: pointer;
}
.submit:disabled { opacity: 0.6; cursor: not-allowed; }
.submit:not(:disabled):hover { background: var(--color-signal-dark); }
.submit-row {
  display: flex;
  gap: 12px;
}
.submit-row .submit { flex: 1; }
.submit.secondary {
  background: #fff;
  color: var(--color-route);
  border: 1px solid var(--color-route);
}

@media (max-width: 768px) {
  .form-view { padding: 28px 16px 56px; }
  .hero h1 { font-size: 28px; }
  .grid { grid-template-columns: 1fr 1fr; }
  .field.wide { grid-column: span 2; }
  .checkboxes { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 560px) {
  .grid { grid-template-columns: 1fr; }
  .field.wide { grid-column: auto; }
  .checkboxes { grid-template-columns: 1fr; }
}
</style>
