import { apiFetch } from "../config/api";
import {
  getChatThreadId,
  hasRenderableVisualization,
  normalizeVisualization,
  setChatThreadId,
} from "./chat";

function parseStoredVisualization(viz) {
  if (!viz) return null;
  let raw = viz;
  if (typeof raw === "string") {
    try {
      raw = JSON.parse(raw);
    } catch {
      return null;
    }
  }
  const normalized = normalizeVisualization(raw);
  return hasRenderableVisualization(normalized) ? normalized : null;
}

/**
 * Convert server conversation messages into ChatScreen query objects.
 * Queries are newest-first (matches ChatScreen state).
 */
export function messagesToQueries(messages = []) {
  const chronological = [...messages];
  const queries = [];
  let current = null;

  for (const msg of chronological) {
    if (msg.role === "user") {
      if (current) queries.push(current);
      const createdAt = msg.created_at
        ? new Date(msg.created_at).getTime()
        : Date.now();
      current = {
        id: msg.id || `${createdAt}-${queries.length}`,
        question: String(msg.content || "").trim(),
        createdAt,
        response: null,
      };
    } else if (msg.role === "assistant" && current) {
      const visualization = parseStoredVisualization(msg.visualization);
      current.response = {
        text: String(msg.content || ""),
        visualization,
        suggestions: Array.isArray(msg.suggestions) ? msg.suggestions : [],
        suggestionMeta: null,
      };
      if (visualization?.visual_type) {
        current.vizType = visualization.visual_type;
      }
      current.status = "complete";
    }
  }
  if (current) queries.push(current);

  return queries.filter((q) => q.question).reverse();
}

export async function listPastConversations(limit = 30) {
  const data = await apiFetch(`/conversations?limit=${limit}`);
  return data.conversations || [];
}

export async function loadConversationById(conversationId) {
  const detail = await apiFetch(
    `/conversations/${conversationId}?message_limit=100`,
  );
  const conv = detail.conversation || {};
  const threadId = conv.external_session_key || getChatThreadId();

  return {
    queries: messagesToQueries(detail.messages || []),
    conversationId: conv.id,
    threadId,
    title: conv.title,
  };
}

export async function loadConversationHistory() {
  const threadId = getChatThreadId();
  const conversations = await listPastConversations(20);

  if (!conversations.length) {
    return { queries: [], threadId, conversationId: null };
  }

  const matched = conversations.find((c) => c.external_session_key === threadId);
  const target = matched || conversations[0];
  const loaded = await loadConversationById(target.id);

  if (loaded.threadId && loaded.threadId !== threadId) {
    setChatThreadId(loaded.threadId);
  }

  return {
    queries: loaded.queries,
    threadId: loaded.threadId,
    conversationId: loaded.conversationId,
  };
}

export function formatConversationWhen(isoString) {
  if (!isoString) return "";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "";
  const now = Date.now();
  const diffMs = now - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
