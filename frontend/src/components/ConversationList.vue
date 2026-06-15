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
      ✏️ 新建规划
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
          🗑
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.conv-list {
  width: 240px;
  height: 100vh;
  background: #1e1e2e;
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0; top: 0;
  padding: 12px 8px;
  box-sizing: border-box;
}

.btn-new {
  width: 100%;
  padding: 10px;
  border: 1px solid #444;
  border-radius: 8px;
  background: transparent;
  color: #e0e0e0;
  cursor: pointer;
  font-size: 14px;
  margin-bottom: 12px;
  text-align: left;
}
.btn-new:hover { background: #2a2a3e; }

.list-body { flex: 1; overflow-y: auto; }
.hint { color: #666; font-size: 13px; padding: 12px 8px; }

.conv-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 8px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  color: #ccc;
  margin-bottom: 2px;
}
.conv-item:hover { background: #2a2a3e; }
.conv-item.active { background: #3a3a5e; color: #fff; }

.dot {
  flex-shrink: 0;
  width: 8px; height: 8px;
  border-radius: 50%;
}
.dot.done   { background: #4ade80; }
.dot.active { background: #f59e0b; }

.info { flex: 1; overflow: hidden; }
.title { font-size: 14px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.meta  { font-size: 12px; color: #888; margin-top: 2px; }

.delete {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #888;
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s, background 0.15s, color 0.15s;
}
.conv-item:hover .delete { opacity: 1; }
.delete:hover { background: #4a2a2a; color: #f87171; }
</style>
