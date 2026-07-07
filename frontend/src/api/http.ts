/**请求底座：带token的fetch+SSE流式读取。其他api/*都复用这里。 */

import { TripPlan } from "../types";
import { getToken, clearAuth } from "../lib/session";

export interface StreamEvent {
  type: "progress" | "need_input" | "done" | "error" | "phase2_start" | "phase2_end";
  message?: string;
  thread_id?: string;
  interrupt_type?: string;
  question?: string;
  trip_plan?: TripPlan | null;
  elapsed_ms?: number;
  failed?: boolean;
}

// 带token的fetch: 自动加Authorization头；401（登录失败）就澄清登录并刷新回登录页面
export async function authFetch(
  url: string,
  options: RequestInit = {},
): Promise<Response> {
  const token = getToken();
  const headers = {
    ...((options.headers as Record<string, string>) ?? {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  const resp = await fetch(url, { ...options, headers });
  if (resp.status === 401) {
    clearAuth();
    location.reload();
  }
  return resp;
}

// POST + 读SSE流（带token)
export async function* streamPost(
  url: string,
  body: any,
): AsyncGenerator<StreamEvent> {
  const token = getToken();
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok || !resp.body) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || `请求失败(${resp.status})`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      if (!part.startsWith("data:")) continue;
      const json = part.slice(5);
      try {
        yield JSON.parse(json) as StreamEvent;
      } catch (e) {
        console.error("[SSE parse", e, json);
      }
    }
  }
}
