/** 历史对话接口：列表/详情/实时状态 /标记完成/删除。均需要登录*/
import type { ConversationItem } from '../types'
import { authFetch } from './http'

export async function fetchConversations():Promise<ConversationItem[]> {
    const resp = await authFetch('/api/conversations')
    if (!resp.ok) return []
    return resp.json()
}

export async function fetchConversation(threadId: string):Promise<any> {
    const resp = await authFetch(`/api/conversations/${threadId}`)
    if (!resp.ok) throw new Error('对话不存在')
    return resp.json()
}

export async function completeConversation(threadId:string):Promise<void>{
    await authFetch(`/api/conversations/${threadId}/complete`,{method:'POST'})
}

export async function deleteConversation(threadId:string):Promise<{ok:boolean, messages:string}>{
    const resp = await authFetch(`/api/conversations/${threadId}`,{method:'DELETE'})
    if (!resp.ok) {
        const err = await resp.json()
        throw new Error(err.detail || '删除失败')
    }
    return resp.json()
}

export async function fetchConvState(threadId: string): Promise<any> {
  const resp = await authFetch(`/api/conversations/${threadId}/state`)
  if (!resp.ok) throw new Error('查询失败')
  return resp.json()
}