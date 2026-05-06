/**
 * 前后端通信。老版本的 SSE 流式接口去掉了 —— 表单式只需要一次性请求。
 */
import type { TripRequest, TripPlan, ChatResponse,ConversationItem } from './types'

export async function planTrip(req: TripRequest): Promise<TripPlan> {
  // 走 vite 代理（见下面 vite.config.ts 配置），所以直接用 /api 相对路径
  const resp = await fetch('/api/plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })

  if (!resp.ok) {
    // 后端 HTTPException 的 detail 在 JSON 的 detail 字段
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail || `请求失败 (${resp.status})`)
  }

  return await resp.json()
}

export async function startChat(req: TripRequest): Promise<ChatResponse> {
  const resp = await fetch('api/chat/start',{
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({request:req})
  })
  if (!resp.ok) {
    const err = await resp.json().catch(()=> ({detail:resp.statusText}))
    throw new Error(err.detail || `请求失败(${resp.status})`)
  }
  return await resp.json()
}

export async function resumeChat(threadId:string,answer:string): Promise<ChatResponse> {
  const resp = await fetch('/api/chat/resume', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ thread_id: threadId, answer }),
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail || `请求失败 (${resp.status})`)
  }
  return await resp.json()
}

// SSE 事件的统一形态
export interface StreamEvent {
  type: 'progress' | 'need_input' | 'done' | 'error'
  message?: string
  thread_id?: string
  interrupt_type?: string
  question?: string
  trip_plan?: TripPlan | null
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
  yield* streamPost('/api/chat/start-stream', { request: req })
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