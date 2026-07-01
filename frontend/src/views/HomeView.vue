<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import type { TripRequest, TripPlan, ConversationItem } from '../types'
import { fetchConversation, fetchConvState } from '../api'
import { clearAuth, getUsername } from '../lib/session'
import ConversationList from '../components/ConversationList.vue'
import FormView from './FormView.vue'
import ChatView from './ChatView.vue'
import ResultView from './ResultView.vue'

type Mode = 'form' | 'chat' | 'result'

const router = useRouter()
const username = getUsername() ?? ''   // 登录后固定，普通常量即可

const mode = ref<Mode>('form')
const loading = ref(false)
const tripPlan = ref<TripPlan | null>(null)
const initialRequest = ref<TripRequest | null>(null)
const activeThreadId = ref<string | null>(null)
const resumeThreadId = ref<string | null>(null)
const resumePlan = ref<TripPlan | null>(null)

const sidebarRef = ref<InstanceType<typeof ConversationList> | null>(null)

// 对话式规划
function handleSubmitChat(req: TripRequest) {
  initialRequest.value = req
  resumeThreadId.value = null
  resumePlan.value = null
  activeThreadId.value = null
  mode.value = 'chat'
}

// 对话完成 → 结果页
function onChatDone(plan: TripPlan) {
  tripPlan.value = plan
  mode.value = 'result'
  sidebarRef.value?.load()   // 刷新侧边栏
}

// 对话中途取消
function cancelChat() {
  mode.value = 'form'
  sidebarRef.value?.load()
}

// 从结果页返回对话继续调整
function backToChat() {
  mode.value = 'chat'
}

// 新建规划（侧边栏按钮）
function startNew() {
  mode.value = 'form'
  tripPlan.value = null
  initialRequest.value = null
  resumeThreadId.value = null
  resumePlan.value = null
  activeThreadId.value = null
}

// 点击历史对话
async function openConversation(conv: ConversationItem) {
  activeThreadId.value = conv.thread_id
  initialRequest.value = null

  try {
    // 优先查完整数据（包含存在 DB 里的 trip_plan）
    const data = await fetchConversation(conv.thread_id)

    // DB 标记了 done 且有 trip_plan → 直接打开结果页
    if (data.status === 'done' && data.trip_plan) {
      tripPlan.value = data.trip_plan
      resumeThreadId.value = conv.thread_id
      resumePlan.value = data.trip_plan
      mode.value = 'result'
      return
    }

    // DB 是 active → 查 LangGraph 实时状态
    const liveState = await fetchConvState(conv.thread_id)

    if (liveState.trip_plan) {
      // 有行程（正在等用户反馈 / 图结束了）→ 直接展示
      tripPlan.value = liveState.trip_plan
      resumeThreadId.value = conv.thread_id
      resumePlan.value = liveState.trip_plan
      mode.value = 'result'
    } else {
      // 真的还在进行中（连行程都没生成完）
      alert('该对话行程尚未生成，请在对话页继续')
    }
  } catch (e: any) {
    alert(`加载失败：${e.message}`)
  }
}

// 退出登录：清 token → 跳登录页（路由守卫也会兜底拦截）
function logout() {
  clearAuth()
  router.push('/login')
}
</script>

<template>
  <div class="app-layout">
    <aside class="sidebar">
      <div class="user-bar">
        <span class="uname">👤 {{ username }}</span>
        <button class="logout-btn" @click="logout">退出</button>
      </div>
      <ConversationList
        ref="sidebarRef"
        :active-thread-id="activeThreadId"
        @new-chat="startNew"
        @open="openConversation"
      />
    </aside>

    <main class="main-content">
      <FormView
        v-show="mode === 'form'"
        :loading="loading"
        @submit-chat="handleSubmitChat"
      />
      <ChatView
        v-if="initialRequest || resumeThreadId"
        v-show="mode === 'chat'"
        :key="resumeThreadId ?? 'new'"
        :initial-request="initialRequest"
        :resume-thread-id="resumeThreadId"
        :resume-plan="resumePlan"
        @done="onChatDone"
        @back="cancelChat"
        @chat-ended="sidebarRef?.load()"
      />
      <ResultView
        v-if="tripPlan"
        v-show="mode === 'result'"
        :trip-plan="tripPlan"
        @back="backToChat"
      />
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}

.sidebar {
  flex-shrink: 0;
  width: 240px;
  height: 100vh;
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
}


.main-content {
  flex: 1;
  min-height: 100vh;
}

.user-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
}
.uname { font-size: 13px; color: #555; }
.logout-btn {
  background: none;
  border: 1px solid #ddd;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  color: #888;
  cursor: pointer;
}
.logout-btn:hover { color: #f56; border-color: #f56; }
</style>
