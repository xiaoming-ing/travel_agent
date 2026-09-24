<script setup lang="ts">
import { nextTick, ref, watch } from "vue";
import type { ChatMessage, TripPlan } from "../../types";

const props = defineProps<{
  messages: ChatMessage[];
  isWaiting: boolean;
  currentPlan: TripPlan | null;
  modelValue: string;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: string];
  send: [];
  "view-plan": [];
}>();

const listEl = ref<HTMLElement | null>(null);

watch(
  () => props.messages.length,
  async () => {
    await nextTick();
    if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight;
  },
);
</script>

<template>
  <aside class="chat-panel">
    <div ref="listEl" class="messages">
      <div
        v-for="(message, index) in messages"
        :key="index"
        class="message"
        :class="message.role"
      >
        <div class="bubble"><pre>{{ message.content }}</pre></div>
      </div>
      <div v-if="isWaiting" class="message agent">
        <div class="bubble typing">正在整理规划...</div>
      </div>
    </div>

    <div class="input-area">
      <input
        :value="modelValue"
        type="text"
        :disabled="isWaiting"
        placeholder="例如：第2天换自然风光 / 酒店换舒适型 / 满意"
        @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
        @keydown.enter="emit('send')"
      />
      <button
        class="btn-send"
        :disabled="isWaiting || !modelValue.trim()"
        @click="emit('send')"
      >
        发送
      </button>
    </div>

    <div v-if="currentPlan" class="done-bar">
      <button class="btn-primary" @click="emit('view-plan')">查看完整行程</button>
    </div>
  </aside>
</template>

<style scoped>
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
.message { display: flex; }
.message.agent { justify-content: flex-start; }
.message.user { justify-content: flex-end; }
.message.system { justify-content: center; }
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
.message.user .bubble { background: var(--color-route); color: #fff; }
.message.system .bubble {
  background: transparent;
  border: none;
  color: var(--color-muted);
  font-size: 12px;
  padding: 4px 8px;
}
.bubble.typing { color: var(--color-route); font-style: normal; }
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
.input-area input:disabled { background: var(--color-soft); color: var(--color-muted); }
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
.btn-send:disabled { opacity: 0.5; cursor: not-allowed; }
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
.btn-primary:hover { background: #195b63; }

@media (max-width: 1100px) {
  .chat-panel { position: static; height: auto; max-height: 50vh; }
}
</style>
