<script setup lang="ts">
import { ref, onMounted, nextTick, computed, onUnmounted } from "vue";
import type { TripRequest, TripPlan, ChatMessage } from "../types";
import {
  startChatStream,
  resumeChatStream,
  completeConversation,
} from "../api";
import type { StreamEvent } from "../api";

import OverviewCard from "../components/trip/OverviewCard.vue";
import BudgetCard from "../components/trip/BudgetCard.vue";
import AttractionMap from "../components/trip/AttractionMap.vue";
import DailyPlan from "../components/trip/DailyPlan.vue";
import HotelList from "../components/trip/HotelList.vue";
import WeatherCard from "../components/trip/WeatherCard.vue";

const props = defineProps<{
  initialRequest?: TripRequest | null;
  resumeThreadId?: string | null;
  resumePlan?: TripPlan | null;
}>();
const emit = defineEmits<{
  done: [plan: TripPlan];
  back: [];
  "chat-ended": []; // 流式结束立即通知父组件
}>();

const messages = ref<ChatMessage[]>([]);
const threadId = ref<string | null>(null);
const currentPlan = ref<TripPlan | null>(null);
const isWaiting = ref(false);
const isDone = ref(false);
const userInput = ref("");
const listEl = ref<HTMLElement | null>(null);
const phase2ElapsedSeconds = ref(0);
const phase2FinalMs = ref<number | null>(null);
const isPhase2Timing = ref(false);

let phase2TimerId: number | null = null;
let phase2StartedAt = 0;

const phase2ElapsedText = computed(() => {
  if (phase2FinalMs.value !== null && !isPhase2Timing.value) {
    return `${(phase2FinalMs.value / 1000).toFixed(1)}秒`;
  }
  return `${phase2ElapsedSeconds.value} 秒`;
});

function startPhase2Timer() {
  stopPhase2Timer();

  phase2ElapsedSeconds.value = 0;
  phase2FinalMs.value = null;
  isPhase2Timing.value = true;
  phase2StartedAt = Date.now();

  phase2TimerId = window.setInterval(() => {
    phase2ElapsedSeconds.value = Math.floor(
      (Date.now() - phase2StartedAt) / 1000,
    );
  }, 1000);
}

function stopPhase2Timer(finalMs?: number) {
  if (phase2TimerId !== null) {
    window.clearInterval(phase2TimerId);
    phase2TimerId = null;
  }

  isPhase2Timing.value = false;

  if (typeof finalMs === "number") {
    phase2FinalMs.value = finalMs;
  }
}

async function scrollToBottom() {
  await nextTick();
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight;
}

function addMessage(role: ChatMessage["role"], content: string) {
  messages.value.push({ role, content, timestamp: Date.now() });
  scrollToBottom();
}

function handleStreamEvent(ev: StreamEvent) {
  if (ev.type === "progress") {
    addMessage("system", ev.message || "");
  } else if (ev.type === "phase2_start") {
    startPhase2Timer();
    addMessage("system", ev.message || "正在整理每日路线...");
  } else if (ev.type === "phase2_end") {
    stopPhase2Timer(ev.elapsed_ms);
    addMessage(
      "system",
      ev.message || `路线整理完成，用时 ${phase2ElapsedText.value}`,
    );
  } else if (ev.type === "need_input") {
    if (ev.thread_id) threadId.value = ev.thread_id;
    if (ev.trip_plan) currentPlan.value = ev.trip_plan;
    addMessage("agent", ev.question || "还需要补充一些信息。");
    emit("chat-ended");
  } else if (ev.type === "done") {
    if (ev.thread_id) threadId.value = ev.thread_id;
    if (ev.trip_plan) currentPlan.value = ev.trip_plan;
    isDone.value = true;
    addMessage("system", "行程已确认，可查看完整计划");
  } else if (ev.type === "error") {
    addMessage("system", `错误：${ev.message}`);
  }
}

async function kickoff() {
  if (props.resumeThreadId) {
    threadId.value = props.resumeThreadId;
    currentPlan.value = props.resumePlan ?? null;
    isDone.value = true;
    addMessage("system", "已恢复该行程，可继续输入修改意见");
    return;
  }

  if (!props.initialRequest) return;

    addMessage("system", `开始规划：${props.initialRequest.destination}`);
  isWaiting.value = true;
  try {
    for await (const ev of startChatStream(props.initialRequest)) {
      handleStreamEvent(ev);
    }
  } catch (e: any) {
    addMessage("system", `会话启动失败：${e.message}`);
  } finally {
    isWaiting.value = false;
  }
}

async function sendMessage() {
  const text = userInput.value.trim();
  if (!text || isWaiting.value || !threadId.value) return;

  addMessage("user", text);
  userInput.value = "";
  isWaiting.value = true;
  try {
    for await (const ev of resumeChatStream(threadId.value, text)) {
      handleStreamEvent(ev);
    }
  } catch (e: any) {
    addMessage("system", `发送失败：${e.message}`);
  } finally {
    isWaiting.value = false;
  }
}

async function viewFullPlan() {
  if (!currentPlan.value || !threadId.value) return;

  if (!isDone.value) {
    try {
      await completeConversation(threadId.value);
      console.log("[viewFullPlan] ✅ 标记完成成功");
    } catch (e) {
      console.error("[viewFullPlan] ❌ 标记完成失败", e);
    }
  }

  emit("done", currentPlan.value);
}

onMounted(kickoff);
onUnmounted(() => {
  stopPhase2Timer();
});
</script>

<template>
  <div class="chat-view">
    <header class="top-bar">
      <div class="title">规划日志 · 实时预览</div>
    </header>

    <div class="layout">
      <!-- 左侧：聊天面板 -->
      <aside class="chat-panel">
        <div ref="listEl" class="messages">
          <div
            v-for="(msg, i) in messages"
            :key="i"
            class="message"
            :class="msg.role"
          >
            <div class="bubble">
              <pre>{{ msg.content }}</pre>
            </div>
          </div>
          <div v-if="isWaiting" class="message agent">
            <div class="bubble typing">正在整理规划...</div>
          </div>
        </div>

        <div class="input-area">
          <input
            v-model="userInput"
            type="text"
            :disabled="isWaiting"
            placeholder="例如：第2天换自然风光 / 酒店换舒适型 / 满意"
            @keydown.enter="sendMessage"
          />
          <button
            class="btn-send"
            :disabled="isWaiting || !userInput.trim()"
            @click="sendMessage"
          >
            发送
          </button>
        </div>

        <div v-if="currentPlan" class="done-bar">
          <button class="btn-primary" @click="viewFullPlan">
            查看完整行程
          </button>
        </div>
      </aside>

      <!-- 右侧：行程实时预览 -->
      <main class="preview">
        <div v-if="!currentPlan" class="empty">
          <div class="empty-icon">路线</div>
          <div class="empty-text">
            {{ isPhase2Timing ? "正在整理每日路线..." : "正在收集旅行数据..." }}
          </div>

          <div class="empty-hint">
            <template v-if="isPhase2Timing || phase2FinalMs !== null">
              规划已用时 {{ phase2ElapsedText }}
            </template>
            <template v-else> 景点、天气、酒店数据准备中 </template>
          </div>
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
  padding: 28px;
}

.top-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
}
.btn-back {
  padding: 6px 14px;
  border: 1px solid var(--color-border);
  background: #fff;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  color: var(--color-ink);
}
.btn-back:hover {
  background: var(--color-soft);
}
.title {
  font-size: 20px;
  font-weight: 750;
  color: var(--color-ink);
}

.layout {
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 18px;
  align-items: start;
}

/* ===== 左侧聊天面板 ===== */
.chat-panel {
  position: sticky;
  top: 24px;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-soft);
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
  background: #fbfaf6;
}
.message {
  display: flex;
}
.message.agent {
  justify-content: flex-start;
}
.message.user {
  justify-content: flex-end;
}
.message.system {
  justify-content: center;
}

.bubble {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.6;
}
.bubble pre {
  margin: 0;
  font-family: inherit;
  white-space: pre-wrap;
  word-break: break-word;
}
.message.agent .bubble {
  background: #fff;
  border: 1px solid var(--color-border);
  color: var(--color-ink);
}
.message.user .bubble {
  background: var(--color-route);
  color: #fff;
}
.message.system .bubble {
  background: transparent;
  border: none;
  color: var(--color-muted);
  font-size: 12px;
  padding: 4px 8px;
}
.bubble.typing {
  color: var(--color-route);
  font-style: normal;
}

.input-area {
  display: flex;
  gap: 8px;
  padding: 12px 14px;
  background: #fff;
  border-top: 1px solid var(--color-border);
}
.input-area input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  font-size: 13px;
  outline: none;
}
.input-area input:focus {
  border-color: var(--color-route);
  box-shadow: 0 0 0 3px rgba(31, 111, 120, 0.12);
}
.input-area input:disabled {
  background: var(--color-soft);
  color: var(--color-muted);
}
.btn-send {
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: var(--color-signal);
  color: #fff;
  font-weight: 750;
  cursor: pointer;
  font-size: 13px;
}
.btn-send:not(:disabled):hover { background: var(--color-signal-dark); }
.btn-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.done-bar {
  padding: 12px 14px;
  background: #fff;
  border-top: 1px solid var(--color-border);
  text-align: center;
}
.btn-primary {
  padding: 10px 24px;
  border: none;
  border-radius: 8px;
  background: var(--color-route);
  color: #fff;
  font-weight: 750;
  cursor: pointer;
  font-size: 14px;
}
.btn-primary:hover {
  background: #195b63;
}

/* ===== 右侧预览 ===== */
.preview {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.empty {
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  padding: 80px 40px;
  text-align: center;
  box-shadow: var(--shadow-soft);
}
.empty-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border: 1px solid rgba(31, 111, 120, 0.2);
  border-radius: 50%;
  color: var(--color-route);
  font-size: 13px;
  font-weight: 750;
  margin-bottom: 16px;
}
.empty-text {
  color: var(--color-ink);
  font-size: 15px;
  margin-bottom: 4px;
}
.empty-hint {
  color: var(--color-muted);
  font-size: 12px;
}

.sections {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 窄屏：上下堆叠，聊天面板折到上面 */
@media (max-width: 1100px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .chat-panel {
    position: static;
    height: auto;
    max-height: 50vh;
  }
}
</style>
