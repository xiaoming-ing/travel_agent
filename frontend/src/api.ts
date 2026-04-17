export interface ChatResponse {
  reply: string
  destination: string | null
  dates: Record<string, any> | null
  budget: number | null
  info_complete: boolean
}

export interface DoneData {
  destination: string | null
  dates: Record<string, any> | null
  budget: number | null
  info_complete: boolean
}

export interface StreamHandlers {
  onMessage?: (content: string) => void                      // supervisor 完整回复
  onStepStart?: (node: string, label: string) => void        // 某步骤开始
  onToken?: (content: string, node: string) => void          // LLM token（带节点名）
  onStepDone?: (node: string, summary: string) => void       // 某步骤完成
  onDone?: (data: DoneData) => void
  onError?: (err: Error) => void
}


export async function sendMessage(message: string, threadId: string): Promise<ChatResponse> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, thread_id: threadId }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function sendMessageStream(message:string,threadId:string,handlers:StreamHandlers): Promise<void> {
  try {
    const res = await fetch('/api/chat/stream',{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({message,thread_id:threadId})
    })
    if (!res.ok || !res.body) throw new Error(`HTTP${res.status}`)
    
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const {value,done} = await reader.read()
      if (done) break
      buffer += decoder.decode(value,{stream:true})

      // SSE事件以\n\n分隔
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''

      for (const raw of parts) {
        if (!raw.trim()) continue
        let event = 'message'
        let dataStr = ''
        for (const line of raw.split('\n')) {
          if (line.startsWith('event:')) event = line.slice(6).trim()
          else if (line.startsWith('data:')) dataStr += line.slice(5).trim()
        }
        if (!dataStr) continue
        const data = JSON.parse(dataStr)

        if (event === 'message')    handlers.onMessage?.(data.content)
        else if (event === 'step_start')  handlers.onStepStart?.(data.node, data.label)
        else if (event === 'token')       handlers.onToken?.(data.content, data.node)
        else if (event === 'step_done')   handlers.onStepDone?.(data.node, data.summary ?? '')
        else if (event === 'done')        handlers.onDone?.(data)

      }
    }
  } catch (e:any) {
    handlers.onError?.(e)
  }
}