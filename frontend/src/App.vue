<script setup lang="ts">
import { ref, nextTick } from "vue";
import { sendMessageStream } from "./api";

interface Msg {
  role: "user" | "assistant";
  content: string;
}
interface Step {
  node: string
  label: string
  content: string
  done: boolean
}

const steps = ref<Step[]>([])
const streamingContent = ref('')  // summarizer 的流式输出，完成后移入 messages

const threadId = `thread-${Date.now()}`;
const messages = ref<Msg[]>([]);
const input = ref("");
const sending = ref(false); // 是否正在流失接收
const status = ref(""); // 当前agent状态提示，如“正在查询天气”
const info = ref<{
  destination: string | null;
  dates: any;
  budget: number | null;
  complete: boolean;
}>({
  destination: null,
  dates: null,
  budget: null,
  complete: false,
});
const listEl = ref<HTMLElement | null>(null);

async function send() {
  const text = input.value.trim();
  if (!text || sending.value) return;

  messages.value.push({ role: "user", content: text });
  input.value = "";
  sending.value = true;
  status.value = "思考中...";
  await scrollToBottom();

  try {
    await sendMessageStream(text, threadId, {
      onMessage: (content) => {
        // supervisor 的回复，直接作为一条完整消息
        messages.value.push({ role: "assistant", content });
        status.value = "";
        scrollToBottom();
      },
      onStepStart: (node, label) => {
        if (node === "summarizer") {
          // summarizer 不放进 step 卡片，用 streamingContent 单独展示
          status.value = label;
        } else {
          steps.value.push({ node, label, content: "", done: false });
        }
        scrollToBottom();
      },
      onToken: (content, node) => {
        if (node === "summarizer") {
          streamingContent.value += content;
        } else {
          const step = steps.value.find((s) => s.node === node);
          if (step) step.content += content;
        }
        scrollToBottom();
      },
      onStepDone: (node, summary) => {
        const step = steps.value.find((s) => s.node === node);
        if (step) {
          step.done = true;
          // 兜底：如果 token 没流出来，用 summary 填充
          if (!step.content && summary) step.content = summary;
        }
        scrollToBottom();
      },
      onDone: (data) => {
        // 把 summarizer 的流式内容移入正式消息
        if (streamingContent.value) {
          messages.value.push({
            role: "assistant",
            content: streamingContent.value,
          });
          streamingContent.value = "";
        }
        // 清除中间步骤
        steps.value = [];
        // 更新信息栏
        info.value = {
          destination: data.destination,
          dates: data.dates,
          budget: data.budget,
          complete: data.info_complete,
        };
      },
      onError: (err) => {
        messages.value.push({
          role: "assistant",
          content: `出错了：${err.message}`,
        });
      },
    });
  } catch (e: any) {
    messages.value.push({ role: "assistant", content: `出错了：${e.message}` });
  } finally {
    sending.value = false;
    status.value = "";
    await scrollToBottom();
  }
}

async function scrollToBottom() {
  await nextTick();
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight;
}
</script>

<template>
  <div class="app">
    <header>
      <h1>🌍 旅行智能助手</h1>
      <div class="info">
        <span :class="{ filled: info.destination }"
          >目的地: {{ info.destination || "未定" }}</span
        >
        <span :class="{ filled: info.dates }"
          >日期: {{ info.dates ? JSON.stringify(info.dates) : "未定" }}</span
        >
        <span :class="{ filled: info.budget }"
          >预算: {{ info.budget ? `¥${info.budget}` : "未定" }}</span
        >
        <span v-if="info.complete" class="complete">✅ 信息齐全</span>
      </div>
    </header>

    <main ref="listEl" class="messages">
      <div v-if="messages.length === 0 && !sending" class="empty">
        开始和助手聊聊你的旅行计划吧～
      </div>
      <div v-for="(m, i) in messages" :key="i" :class="['msg', m.role]">
        <div class="bubble">{{ m.content }}</div>
      </div>

      <!-- 规划步骤卡片（中间过程，完成后消失） -->
      <div v-if="steps.length > 0" class="planning-steps">
        <div
          v-for="step in steps"
          :key="step.node"
          class="step-card"
          :class="{ 'step-done': step.done }"
        >
          <div class="step-header">
            <span v-if="!step.done" class="step-spinner"></span>
            <span v-else class="step-check">✓</span>
            <span>{{ step.label }}</span>
          </div>
          <div v-if="step.content" class="step-body">{{ step.content }}</div>
        </div>
      </div>

      <!-- summarizer 流式输出（完成后移入 messages） -->
      <div v-if="streamingContent" class="msg assistant">
        <div class="bubble">{{ streamingContent }}</div>
      </div>

      <!-- 状态指示器（仅在无步骤卡片时显示） -->
      <div v-if="sending && status && steps.length === 0" class="status-bar">
        <span class="dot"></span>{{ status }}
      </div>
    </main>

    <footer>
      <input
        v-model="input"
        @keydown.enter="send"
        :disabled="sending"
        placeholder="例如：我想下周去三亚玩3天"
      />
      <button @click="send" :disabled="sending || !input.trim()">发送</button>
    </footer>
  </div>
</template>

<style>
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}
body {
  font-family: -apple-system, "PingFang SC", sans-serif;
  background: #f5f5f7;
}

.app {
  max-width: 800px;
  margin: 0 auto;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fff;
}

header {
  padding: 16px 20px;
  border-bottom: 1px solid #eee;
  background: #fff;
}
header h1 {
  font-size: 18px;
  margin-bottom: 8px;
}
.info {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: #999;
}
.info .filled {
  color: #1677ff;
  font-weight: 500;
}
.info .complete {
  color: #52c41a;
  font-weight: 600;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.empty {
  text-align: center;
  color: #bbb;
  margin-top: 60px;
}

.msg {
  display: flex;
}
.msg.user {
  justify-content: flex-end;
}
.msg.assistant {
  justify-content: flex-start;
}
.bubble {
  max-width: 70%;
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg.user .bubble {
  background: #1677ff;
  color: #fff;
}
.msg.assistant .bubble {
  background: #f0f0f0;
  color: #333;
}
.bubble.loading {
  opacity: 0.6;
}

footer {
  display: flex;
  gap: 8px;
  padding: 16px 20px;
  border-top: 1px solid #eee;
}
input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
}
input:focus {
  border-color: #1677ff;
}
button {
  padding: 10px 20px;
  background: #1677ff;
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}
button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.status-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  font-size: 12px;
  color: #888;
}
.status-bar .dot {
  width: 6px;
  height: 6px;
  background: #1677ff;
  border-radius: 50%;
  animation: pulse 1s infinite;
}
@keyframes pulse {
  0%,
  100% {
    opacity: 0.3;
  }
  50% {
    opacity: 1;
  }
}
.planning-steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 0;
}
.step-card {
  background: #fafafa;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  transition: opacity 0.3s;
}
.step-card.step-done {
  opacity: 0.7;
}
.step-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
  color: #555;
}
.step-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid #1677ff;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.step-check {
  color: #52c41a;
  font-weight: bold;
}
.step-body {
  margin-top: 6px;
  color: #666;
  line-height: 1.5;
  white-space: pre-wrap;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
