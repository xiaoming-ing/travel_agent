<script setup lang="ts">
import { ref, computed } from 'vue'
import { login, register } from '../api'
import { setAuth } from '../lib/session'
import { useRouter } from 'vue-router'

const router = useRouter()

const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const error = ref('')
const submitting = ref(false)

const isLogin = computed(() => mode.value === 'login')

async function submit() {
  if (submitting.value) return   // 防抖:回车/点击都会走这里,避免连续触发重复提交
  error.value = ''
  if (!username.value || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }
  if (mode.value === 'register' && password.value.length < 6) {
    error.value = '密码至少 6 位'
    return
  }
  submitting.value = true
  try {
    const fn = isLogin.value ? login : register
    const res = await fn(username.value, password.value)
    setAuth(res.token, res.username)   // 存 token + 用户名
    router.push('/')                    // 让 App.vue 显示主应用
  } catch (e: any) {
    error.value = e.message || '操作失败'
  } finally {
    submitting.value = false
  }
}

function toggleMode() {
  mode.value = isLogin.value ? 'register' : 'login'
  error.value = ''
}
</script>

<template>
  <div class="auth-bg">
    <div class="auth-card">
      <h1>旅行规划工作台</h1>
      <p class="subtitle">{{ isLogin ? '登录你的账号' : '注册新账号' }}</p>

      <div class="field">
        <label>用户名</label>
        <input v-model="username" type="text" placeholder="请输入用户名" @keyup.enter="submit" />
      </div>

      <div class="field">
        <label>密码</label>
        <input v-model="password" type="password" placeholder="请输入密码" @keyup.enter="submit" />
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <button class="submit" :disabled="submitting" @click="submit">
        {{ submitting ? '处理中…' : (isLogin ? '登录' : '注册') }}
      </button>

      <p class="toggle">
        {{ isLogin ? '还没有账号?' : '已有账号?' }}
        <a @click="toggleMode">{{ isLogin ? '去注册' : '去登录' }}</a>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-bg {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    linear-gradient(180deg, rgba(255,255,255,0.62), rgba(255,255,255,0) 360px),
    var(--color-paper);
  padding: 24px;
}
.auth-card {
  width: 360px;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  padding: 36px 32px;
  box-shadow: var(--shadow-soft);
}
.auth-card h1 { font-size: 24px; text-align: center; margin-bottom: 6px; color: var(--color-ink); }
.subtitle { text-align: center; color: var(--color-note); margin-bottom: 28px; font-size: 14px; }
.field { margin-bottom: 18px; }
.field label { display: block; font-size: 13px; color: var(--color-note); margin-bottom: 6px; font-weight: 650; }
.field input {
  width: 100%;
  padding: 11px 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  font-size: 14px;
  outline: none;
}
.field input:focus {
  border-color: var(--color-route);
  box-shadow: 0 0 0 3px rgba(31, 111, 120, 0.12);
}
.error { color: var(--color-signal); font-size: 13px; margin-bottom: 14px; }
.submit {
  width: 100%;
  padding: 13px;
  background: var(--color-signal);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 750;
  cursor: pointer;
}
.submit:disabled { opacity: 0.6; cursor: not-allowed; }
.submit:not(:disabled):hover { background: var(--color-signal-dark); }
.toggle { text-align: center; margin-top: 18px; font-size: 13px; color: var(--color-note); }
.toggle a { color: var(--color-route); cursor: pointer; margin-left: 4px; }
</style>
