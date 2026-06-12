import { authFetch, parseErrorResponse, resolveApiBase } from "../config/api";

export async function startVisualizeSession(items, chatSessionId = null) {
  const res = await authFetch("/visualize/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      items,
      chat_session_id: chatSessionId,
    }),
  });
  if (!res.ok) {
    throw new Error(await parseErrorResponse(res, "Could not start Visualize session"));
  }
  return res.json();
}

export async function streamVisualizeChat({ sessionId, message, items, onEvent }) {
  const res = await authFetch("/visualize/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      items: items || undefined,
    }),
  });

  if (!res.ok) {
    throw new Error(await parseErrorResponse(res, "Visualize chat failed"));
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

export async function fetchVisualizeThemes() {
  const res = await authFetch("/visualize/themes");
  if (!res.ok) {
    throw new Error(await parseErrorResponse(res, "Could not load themes"));
  }
  const body = await res.json();
  return body.themes || [];
}

export async function fetchVisualizeLayouts() {
  const res = await authFetch("/visualize/layouts");
  if (!res.ok) {
    throw new Error(await parseErrorResponse(res, "Could not load layouts"));
  }
  const body = await res.json();
  return body.layouts || [];
}

async function postVisualizeJson(path, body) {
  const res = await authFetch(`/visualize/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(await parseErrorResponse(res, `Visualize ${path} failed`));
  }
  return res.json();
}

export async function inspectVisualizeData(items) {
  const body = await postVisualizeJson("inspect", { items });
  return body.inspection;
}

export async function analyzeVisualizeData(items, inspection = null) {
  return postVisualizeJson("analyze", { items, inspection });
}

export async function recommendVisualizeFormat(inspection, analysis) {
  const body = await postVisualizeJson("recommend", { inspection, analysis });
  return body.recommendation;
}

export async function runVisualizeBrain(items) {
  return postVisualizeJson("brain", { items });
}

export async function buildVisualizeReport({
  sessionId,
  format,
  theme,
  layout,
  includeLogo = true,
  pageNumbers = true,
  watermark = "none",
  title,
}) {
  const body = await postVisualizeJson("build", {
    session_id: sessionId,
    format,
    theme,
    layout,
    include_logo: includeLogo,
    page_numbers: pageNumbers,
    watermark,
    title,
  });
  return body.output;
}

function rewriteLocalhostUrl(url) {
  try {
    const parsed = new URL(url);
    if (parsed.hostname !== "localhost" && parsed.hostname !== "127.0.0.1") {
      return url;
    }
    return `${resolveApiBase()}${parsed.pathname}${parsed.search}`;
  } catch {
    return url;
  }
}

export function resolveOutputUrl(output) {
  if (!output) return null;
  const path = output.pdf_url || output.excel_url || output.download_url;
  if (!path) return null;
  if (path.startsWith("http")) return rewriteLocalhostUrl(path);
  return `${resolveApiBase()}${path}`;
}
