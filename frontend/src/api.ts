/**
 * 前后端通信。老版本的 SSE 流式接口去掉了 —— 表单式只需要一次性请求。
 */
import type { TripRequest, TripPlan, ConversationItem } from './types'
import { getUserId } from './userId'

// SSE 事件的统一形态
export interface StreamEvent {
  type: 'progress' | 'need_input' | 'done' | 'error'
  message?: string
  thread_id?: string
  interrupt_type?: string
  question?: string
  trip_plan?: TripPlan | null
}

export interface SavedPreferences {
  preferences: string[]
  accommodation: string
  transport: string
}

// 通用：POST + 读 SSE 流
async function* streamPost(url: string, body: any): AsyncGenerator<StreamEvent> {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!resp.ok || !resp.body) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail || `请求失败 (${resp.status})`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // SSE 报文按 '\n\n' 分隔
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''  // 最后不完整的留到下轮

    for (const part of parts) {
      if (!part.startsWith('data:')) continue
      const json = part.slice(5)
      try {
        yield JSON.parse(json) as StreamEvent
      } catch (e) {
        console.error('[SSE parse]', e, json)
      }
    }
  }
}

export async function* startChatStream(req: TripRequest): AsyncGenerator<StreamEvent> {
  yield* streamPost('/api/chat/start-stream', { request: req, user_id: getUserId() })
}

export async function* resumeChatStream(threadId: string, answer: string): AsyncGenerator<StreamEvent> {
  yield* streamPost('/api/chat/resume-stream', { thread_id: threadId, answer })
}

export async function fetchConversations(): Promise<ConversationItem[]> {
  const resp = await fetch('/api/conversations')
  if (!resp.ok) return []
  return resp.json()
}

export async function fetchConversation(threadId: string): Promise<any> {
  const resp = await fetch(`/api/conversations/${threadId}`)
  if (!resp.ok) throw new Error('对话不存在')
  return resp.json()
}

export async function fetchConvState(threadId: string): Promise<any> {
  const resp = await fetch(`/api/conversations/${threadId}/state`)
  if (!resp.ok) throw new Error('查询失败')
  return resp.json()
}

export async function completeConversation(threadId: string): Promise<void> {
  await fetch(`/api/conversations/${threadId}/complete`, { method: 'POST' })
}

export async function deleteConversation(threadId: string): Promise<{ok:boolean,messages:string}> {
  const res = await fetch(`/api/conversations/${threadId}`, {
    method: 'DELETE'
  })

  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || '删除失败')
  }
  return res.json()
}

export async function getPreferences(userId: string): Promise<SavedPreferences | null> {
  const resp = await fetch(`/api/preferences/${userId}`)
  if (!resp.ok) return null
  const data = await resp.json().catch(() => null)
  if (!data || Object.keys(data).length === 0) return null
  return data as SavedPreferences
}