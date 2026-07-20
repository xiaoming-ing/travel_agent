<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { ConversationItem } from '../types'
import { fetchConversations,deleteConversation } from '../api'

const emit = defineEmits<{
  'new-chat': []
  'open': [conv: ConversationItem]
}>()

const props = defineProps<{ activeThreadId: string | null }>()
const conversations = ref<ConversationItem[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  conversations.value = await fetchConversations()
  loading.value = false
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

async function handleDelete (threadId:string) {
  try {
    const res = await deleteConversation(threadId)
    if (res.ok) {
      conversations.value = conversations.value.filter(c=>c.thread_id !== threadId)
    }
  } catch (e) {
    console.error(e)
  }
}

onMounted(load)
defineExpose({ load })   // 父组件可以调用 load() 刷新列表
</script>

<template>
  <div class="conv-list">
    <button class="btn-new" @click="emit('new-chat')">
      新建规划
    </button>

    <div class="list-body">
      <div v-if="loading" class="hint">加载中...</div>
      <div v-else-if="conversations.length === 0" class="hint">暂无历史</div>

      <div
        v-for="c in conversations"
        :key="c.thread_id"
        class="conv-item"
        :class="{ active: c.thread_id === activeThreadId }"
        @click="emit('open', c)"
      >
        <span class="dot" :class="c.status" />
        <div class="info">
          <div class="title">{{ c.destination }}</div>
          <div class="meta">{{ formatDate(c.created_at) }} · {{ c.status === 'done' ? '已完成' : '进行中' }}</div>
        </div>
        <button class="delete" title="删除" @click.stop="handleDelete(c.thread_id)">
          删除
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.conv-list {
  width: 100%;
  flex: 1;
  min-height: 0;
  background: transparent;
  display: flex;
  flex-direction: column;
  padding: 0 14px 14px;
  box-sizing: border-box;
}


.btn-new {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--color-signal);
  border-radius: 8px;
  background: var(--color-signal);
  color: #fff;
  cursor: pointer;
  font-size: 14px;
  font-weight: 650;
  margin-bottom: 12px;
  text-align: left;
}
.btn-new:hover { background: var(--color-signal-dark); border-color: var(--color-signal-dark); }

.list-body { flex: 1; overflow-y: auto; }
.hint { color: var(--color-muted); font-size: 13px; padding: 12px 8px; }

.conv-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  color: var(--color-note);
  margin-bottom: 4px;
}
.conv-item:hover { background: rgba(255,255,255,0.7); border-color: var(--color-border); }
.conv-item.active {
  background: #fff;
  border-color: rgba(31, 111, 120, 0.28);
  color: var(--color-ink);
  box-shadow: 0 6px 18px rgba(31, 41, 51, 0.05);
}

.dot {
  flex-shrink: 0;
  width: 8px; height: 8px;
  border-radius: 50%;
}
.dot.done   { background: var(--color-route); }
.dot.active { background: var(--color-signal); }

.info { flex: 1; overflow: hidden; }
.title { font-size: 14px; font-weight: 650; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.meta  { font-size: 12px; color: var(--color-muted); margin-top: 2px; }

.delete {
  flex-shrink: 0;
  width: auto;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 5px;
  background: transparent;
  color: var(--color-muted);
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s, background 0.15s, color 0.15s;
}
.conv-item:hover .delete { opacity: 1; }
.delete:hover { background: #f8e7e0; color: var(--color-signal); }
</style>
