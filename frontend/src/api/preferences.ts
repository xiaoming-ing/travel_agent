/**长期记忆：读取当前登录用户的偏好画像，供表单预选。 */
import { authFetch } from "./http"

export interface SavedPreferences {
    preferences: string[]
    accommodation:string
    transport:string
}

export async function getPreferences():Promise<SavedPreferences | null> {
    const resp = await authFetch('/api/preferences')
    if (!resp.ok) return null
    const data = await resp.json().catch(()=> null)
    if (!data || Object.keys(data).length === 0) return null
    return data as SavedPreferences
}