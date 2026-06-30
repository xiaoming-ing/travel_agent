/** 会话接口：开新会话 / 续跑（均为SSE流式）。 */

import { TripRequest } from "../types";
import { streamPost, type StreamEvent } from "./http";

export async function* startChatStream(
  req: TripRequest,
): AsyncGenerator<StreamEvent> {
  yield* streamPost("/api/chat/start-stream", { request: req });
}

export async function* resumeChatStream(
  threadId: string,
  answer: string,
): AsyncGenerator<StreamEvent> {
  yield* streamPost("/api/chat/resume-stream", { thread_id: threadId, answer });
}
