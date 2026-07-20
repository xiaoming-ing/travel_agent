<script setup lang="ts">
import { ref, computed } from 'vue'
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
const avatarLetter = computed(() => username ? username.charAt(0).toUpperCase() : '?')

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
  loading.value = true   // 防抖:切回 form 页时才解除,避免按钮被连续点击触发多次提交
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
  loading.value = false
  sidebarRef.value?.load()
}

// 从结果页返回对话继续调整
function backToChat() {
  mode.value = 'chat'
}

// 新建规划（侧边栏按钮）
function startNew() {
  mode.value = 'form'
  loading.value = false
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
        <div class="user-info">
          <span class="avatar">{{ avatarLetter }}</span>
          <span class="uname">{{ username }}</span>
        </div>
        <router-link to="/knowledge" class="kb-link" title="我的攻略库">攻略库</router-link>
        <button class="logout-btn" title="退出登录" aria-label="退出登录" @click="logout">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4" />
            <path d="M9 8l-4 4 4 4" />
            <path d="M5 12h11" />
          </svg>
        </button>
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
  background:
    linear-gradient(90deg, rgba(31, 111, 120, 0.05) 0, transparent 360px),
    var(--color-paper);
}

.sidebar {
  flex-shrink: 0;
  width: 260px;
  height: 100vh;
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
}


.main-content {
  flex: 1;
  min-height: 100vh;
}

.user-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 14px;
  padding: 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  background: var(--color-surface);
}
.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;   /* 允许 .uname 超长时正常省略 */
}
.avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-route);
  color: #fff;
  font-size: 14px;
  font-weight: 700;
}
.uname {
  font-size: 13px;
  color: var(--color-ink);
  font-weight: 650;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.logout-btn {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  background: none;
  border: none;
  border-radius: 6px;
  color: var(--color-muted);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.logout-btn:hover { background: #f8e7e0; color: var(--color-signal); }
.kb-link {
  text-decoration: none;
  font-size: 12px;
  padding: 7px 8px;
  border-radius: 6px;
  color: var(--color-route);
  border: 1px solid transparent;
  white-space: nowrap;
}
.kb-link:hover { background: #edf5f4; border-color: rgba(31, 111, 120, 0.18); }

</style>
