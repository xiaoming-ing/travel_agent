<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { completeConversation, resumeChatStream, startChatStream } from "../api";
import type { StreamEvent } from "../api";
import ChatPanel from "../components/chat/ChatPanel.vue";
import PlanPreview from "../components/chat/PlanPreview.vue";
import type { ChatMessage, TripPlan, TripRequest } from "../types";

const props = defineProps<{
  initialRequest?: TripRequest | null;
  resumeThreadId?: string | null;
  resumePlan?: TripPlan | null;
}>();
const emit = defineEmits<{
  done: [plan: TripPlan];
  back: [];
  "chat-ended": [];
}>();

const messages = ref<ChatMessage[]>([]);
const threadId = ref<string | null>(null);
const currentPlan = ref<TripPlan | null>(null);
const isWaiting = ref(false);
const isDone = ref(false);
const userInput = ref("");
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
    phase2ElapsedSeconds.value = Math.floor((Date.now() - phase2StartedAt) / 1000);
  }, 1000);
}

function stopPhase2Timer(finalMs?: number) {
  if (phase2TimerId !== null) {
    window.clearInterval(phase2TimerId);
    phase2TimerId = null;
  }
  isPhase2Timing.value = false;
  if (typeof finalMs === "number") phase2FinalMs.value = finalMs;
}

function addMessage(role: ChatMessage["role"], content: string) {
  messages.value.push({ role, content, timestamp: Date.now() });
}

function handleStreamEvent(event: StreamEvent) {
  if (event.type === "progress") {
    addMessage("system", event.message || "");
  } else if (event.type === "phase2_start") {
    startPhase2Timer();
    addMessage("system", event.message || "正在整理每日路线...");
  } else if (event.type === "phase2_end") {
    stopPhase2Timer(event.elapsed_ms);
    addMessage("system", event.message || `路线整理完成，用时 ${phase2ElapsedText.value}`);
  } else if (event.type === "need_input") {
    if (event.thread_id) threadId.value = event.thread_id;
    if (event.trip_plan) currentPlan.value = event.trip_plan;
    addMessage("agent", event.question || "还需要补充一些信息。");
    emit("chat-ended");
  } else if (event.type === "done") {
    if (event.thread_id) threadId.value = event.thread_id;
    if (event.trip_plan) currentPlan.value = event.trip_plan;
    isDone.value = true;
    addMessage("system", "行程已确认，可查看完整计划");
  } else if (event.type === "error") {
    addMessage("system", `错误：${event.message}`);
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
    for await (const event of startChatStream(props.initialRequest)) {
      handleStreamEvent(event);
    }
  } catch (error: any) {
    addMessage("system", `会话启动失败：${error.message}`);
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
    for await (const event of resumeChatStream(threadId.value, text)) {
      handleStreamEvent(event);
    }
  } catch (error: any) {
    addMessage("system", `发送失败：${error.message}`);
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
    } catch (error) {
      console.error("[viewFullPlan] ❌ 标记完成失败", error);
    }
  }
  emit("done", currentPlan.value);
}

onMounted(kickoff);
onUnmounted(stopPhase2Timer);
</script>

<template>
  <div class="chat-view">
    <header class="top-bar"><div class="title">规划日志 · 实时预览</div></header>
    <div class="layout">
      <ChatPanel
        v-model="userInput"
        :messages="messages"
        :is-waiting="isWaiting"
        :current-plan="currentPlan"
        @send="sendMessage"
        @view-plan="viewFullPlan"
      />
      <PlanPreview
        :plan="currentPlan"
        :is-phase2-timing="isPhase2Timing"
        :phase2-final-ms="phase2FinalMs"
        :phase2-elapsed-text="phase2ElapsedText"
      />
    </div>
  </div>
</template>

<style scoped>
.chat-view { max-width: 1400px; margin: 0 auto; padding: 28px; }
.top-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; }
.title { font-size: 20px; font-weight: 750; color: var(--color-ink); }
.layout {
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 18px;
  align-items: start;
}
@media (max-width: 1100px) {
  .layout { grid-template-columns: 1fr; }
}
</style>
