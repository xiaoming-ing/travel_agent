/**登录态：把token和用户名存在localStorage,全局可读。 */

const TOKEN_KEY = 'travel_token'
const NAME_KEY = 'travel_username'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function getUsername():string | null {
  return localStorage.getItem(NAME_KEY)
}

export function isLoggedIn():boolean {
  return !!getToken()
}

export function setAuth(token:string,username:string):void {
  localStorage.setItem(TOKEN_KEY,token)
  localStorage.setItem(NAME_KEY,username)
}

export function clearAuth():void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(NAME_KEY)
}
