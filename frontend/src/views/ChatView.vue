<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import type { TripRequest, TripPlan, ChatMessage, ChatResponse } from '../types'
import { startChatStream, resumeChatStream, completeConversation } from '../api'
import type { StreamEvent } from '../api'


import OverviewCard from '../components/OverviewCard.vue'
import BudgetCard from '../components/BudgetCard.vue'
import AttractionMap from '../components/AttractionMap.vue'
import DailyPlan from '../components/DailyPlan.vue'
import HotelList from '../components/HotelList.vue'
import WeatherCard from '../components/WeatherCard.vue'

const props = defineProps<{ initialRequest: TripRequest }>()
const emit = defineEmits<{
  done: [plan: TripPlan]
  back: []
  'chat-ended': [] // 流式结束立即通知父组件
}>()

const messages = ref<ChatMessage[]>([])
const threadId = ref<string | null>(null)
const currentPlan = ref<TripPlan | null>(null)
const isWaiting = ref(false)
const isDone = ref(false)
const userInput = ref('')
const listEl = ref<HTMLElement | null>(null)

async function scrollToBottom() {
  await nextTick()
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
}

function addMessage(role: ChatMessage['role'], content: string) {
  messages.value.push({ role, content, timestamp: Date.now() })
  scrollToBottom()
}

function handleStreamEvent(ev: StreamEvent) {
  if (ev.type === 'progress') {
    addMessage('system', ev.message || '')
  } else if (ev.type === 'need_input') {
    if (ev.thread_id) threadId.value = ev.thread_id
    if (ev.trip_plan) currentPlan.value = ev.trip_plan
    addMessage('agent', ev.question || '（Agent 没说话）')
    emit('chat-ended') 
  } else if (ev.type === 'done') {
    if (ev.thread_id) threadId.value = ev.thread_id
    if (ev.trip_plan) currentPlan.value = ev.trip_plan
    isDone.value = true
    addMessage('system', '对话结束，可点击下方按钮查看完整行程')
  } else if (ev.type === 'error') {
    addMessage('system', `错误：${ev.message}`)
  }
}


async function kickoff() {
  addMessage('system', `开始规划：${props.initialRequest.destination}`)
  isWaiting.value = true
  try {
    for await (const ev of startChatStream(props.initialRequest)) {
      handleStreamEvent(ev)
    }
  } catch (e: any) {
    addMessage('system', `会话启动失败：${e.message}`)
  } finally {
    isWaiting.value = false
  }
}


async function sendMessage() {
  const text = userInput.value.trim()
  if (!text || isWaiting.value || isDone.value || !threadId.value) return

  addMessage('user', text)
  userInput.value = ''
  isWaiting.value = true
  try {
    for await (const ev of resumeChatStream(threadId.value, text)) {
      handleStreamEvent(ev)
    }
  } catch (e: any) {
    addMessage('system', `发送失败：${e.message}`)
  } finally {
    isWaiting.value = false
  }
}

async function viewFullPlan() {
  if (!currentPlan.value || !threadId.value) return

  if (!isDone.value) {
    try {
      await completeConversation(threadId.value)
      console.log('[viewFullPlan] ✅ 标记完成成功')
    } catch (e) {
      console.error('[viewFullPlan] ❌ 标记完成失败', e)
    }
  }

  emit('done', currentPlan.value)
}

onMounted(kickoff)
</script>

<template>
  <div class="chat-view">
    <header class="top-bar">
      <button class="btn-back" @click="emit('back')">← 返回</button>
      <div class="title">对话式行程规划 · 实时预览</div>
    </header>

    <div class="layout">
      <!-- 左侧：聊天面板 -->
      <aside class="chat-panel">
        <div ref="listEl" class="messages">
          <div v-for="(msg, i) in messages" :key="i" class="message" :class="msg.role">
            <div class="bubble"><pre>{{ msg.content }}</pre></div>
          </div>
          <div v-if="isWaiting" class="message agent">
            <div class="bubble typing">Agent 思考中…</div>
          </div>
        </div>

        <div class="input-area">
          <input
            v-model="userInput"
            type="text"
            :disabled="isWaiting || isDone"
            placeholder="Day 2 换自然风光 / 酒店换豪华 / 满意"
            @keydown.enter="sendMessage"
          />
          <button
            class="btn-send"
            :disabled="isWaiting || isDone || !userInput.trim()"
            @click="sendMessage"
          >
            发送
          </button>
        </div>

        <div v-if="currentPlan" class="done-bar">
          <button class="btn-primary" @click="viewFullPlan">
            查看完整行程 →
          </button>
          <button class="btn-secondary" @click="emit('back')">
            重新规划
          </button>
        </div>
      </aside>

      <!-- 右侧：行程实时预览 -->
      <main class="preview">
        <div v-if="!currentPlan" class="empty">
          <div class="empty-icon">🗺️</div>
          <div class="empty-text">行程生成中，请稍候…</div>
          <div class="empty-hint">Phase 1 + Phase 2 通常 30~60 秒</div>
        </div>
        <div v-else class="sections">
          <section>
            <OverviewCard
              :destination="currentPlan.destination"
              :start-date="currentPlan.start_date"
              :end-date="currentPlan.end_date"
              :suggestion="currentPlan.suggestion"
            />
          </section>
          <section><BudgetCard :budget="currentPlan.budget" /></section>
          <section>
            <AttractionMap
              :attractions="currentPlan.attractions"
              :hotels="currentPlan.hotels"
            />
          </section>
          <section>
            <DailyPlan
              :daily-plans="currentPlan.daily_plans"
              :all-attractions="currentPlan.attractions"
            />
          </section>
          <section><HotelList :hotels="currentPlan.hotels" /></section>
          <section>
            <WeatherCard
              :destination="currentPlan.destination"
              :weather-summary="currentPlan.weather_summary"
              :suggestion="currentPlan.suggestion"
            />
          </section>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}

.top-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.btn-back {
  padding: 6px 14px;
  border: 1px solid #ddd;
  background: #fff;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  color: #333;
}
.btn-back:hover { background: #f5f5f7; }
.title { font-size: 18px; font-weight: 600; color: #333; }

.layout {
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 20px;
  align-items: start;
}

/* ===== 左侧聊天面板 ===== */
.chat-panel {
  position: sticky;
  top: 24px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  overflow: hidden;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #fafafa;
}
.message { display: flex; }
.message.agent { justify-content: flex-start; }
.message.user { justify-content: flex-end; }
.message.system { justify-content: center; }

.bubble {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.6;
}
.bubble pre {
  margin: 0;
  font-family: inherit;
  white-space: pre-wrap;
  word-break: break-word;
}
.message.agent .bubble { background: #fff; border: 1px solid #eee; color: #333; }
.message.user .bubble {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
}
.message.system .bubble {
  background: transparent;
  border: none;
  color: #999;
  font-size: 12px;
  padding: 4px 8px;
}
.bubble.typing { color: #888; font-style: italic; }

.input-area {
  display: flex;
  gap: 8px;
  padding: 12px 14px;
  background: #fff;
  border-top: 1px solid #eee;
}
.input-area input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 13px;
  outline: none;
}
.input-area input:focus { border-color: #667eea; }
.input-area input:disabled { background: #f5f5f5; color: #999; }
.btn-send {
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  font-size: 13px;
}
.btn-send:disabled { opacity: 0.5; cursor: not-allowed; }

.done-bar {
  padding: 12px 14px;
  background: #fff;
  border-top: 1px solid #eee;
  text-align: center;
}
.btn-primary {
  padding: 10px 24px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #4ade80, #22c55e);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
  font-size: 14px;
}
.btn-primary:hover { opacity: 0.9; }

/* ===== 右侧预览 ===== */
.preview { display: flex; flex-direction: column; gap: 20px; }
.empty {
  background: #fff;
  border-radius: 16px;
  padding: 80px 40px;
  text-align: center;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}
.empty-icon { font-size: 48px; margin-bottom: 16px; }
.empty-text { color: #555; font-size: 15px; margin-bottom: 4px; }
.empty-hint { color: #aaa; font-size: 12px; }

.sections { display: flex; flex-direction: column; gap: 20px; }

/* 窄屏：上下堆叠，聊天面板折到上面 */
@media (max-width: 1100px) {
  .layout { grid-template-columns: 1fr; }
  .chat-panel {
    position: static;
    height: auto;
    max-height: 50vh;
  }
}
</style>
