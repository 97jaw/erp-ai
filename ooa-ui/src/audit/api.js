import { authFetch, parseErrorResponse } from "../config/api";

export async function streamAuditChat({ sessionId, message, onEvent }) {
  const res = await authFetch("/audit/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      message,
    }),
  });

  if (!res.ok) {
    throw new Error(await parseErrorResponse(res, "Audit request failed"));
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        const data = JSON.parse(line.slice(6));
        onEvent?.(data);
      } catch {
        /* ignore malformed chunks */
      }
    }
  }
}
