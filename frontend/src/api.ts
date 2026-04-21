/**
 * 前后端通信。老版本的 SSE 流式接口去掉了 —— 表单式只需要一次性请求。
 */
import type { TripRequest, TripPlan } from './types'

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
