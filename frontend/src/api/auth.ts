/** 认证接口：注册 / 登录。返回的token由调用方进lib/session。 */
export interface AuthResult {
    token: string
    user_id: string
    username:string
}

export async function login(username:string,password:string):Promise<AuthResult> {
    const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ username,password})
    })
    if (!resp.ok) {
        const err = await resp.json().catch(()=> ({}))
        throw new Error(err.detail || '登录失败')
    }
    return resp.json()
}

export async function register(username:string,password:string): Promise<AuthResult> {
    const resp = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json'},
        body: JSON.stringify({ username,password})
    })
    if(!resp.ok) {
        const err = await resp.json().catch(()=> ({}))
        throw new Error(err.detail || '注册失败')
    }
    return resp.json()
}