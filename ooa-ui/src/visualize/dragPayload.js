/**
 * Build / parse drag payloads from main-chat responses.
 * Kept separate from chat utils so Visualize stays isolated.
 */

export function buildVisualizeDragPayload({
  queryId,
  messageId,
  question = "",
  text = "",
  visualization = null,
  vizType = null,
  createdAt = Date.now(),
}) {
  return {
    type: "chat_response",
    id: `${queryId}-${messageId}`,
    queryId,
    messageId,
    question: String(question || "").trim(),
    text: String(text || "").trim(),
    visualization: visualization || null,
    vizType: vizType || visualization?.visual_type || null,
    createdAt,
  };
}

export function parseVisualizeDragPayload(raw) {
  if (!raw) return null;
  try {
    const data = JSON.parse(raw);
    if (data?.type !== "chat_response" || !data.id) return null;
    return data;
  } catch {
    return null;
  }
}

export function labelForDroppedItem(item) {
  if (!item) return "Response";
  const fromQuestion = item.question?.trim();
  if (fromQuestion) {
    return fromQuestion.length > 48 ? `${fromQuestion.slice(0, 48)}…` : fromQuestion;
  }
  const fromText = item.text?.trim();
  if (fromText) {
    return fromText.length > 48 ? `${fromText.slice(0, 48)}…` : fromText;
  }
  if (item.vizType) return item.vizType.replace(/_/g, " ");
  return "Chat response";
}

export function isDuplicateDrop(items, candidate) {
  return items.some((item) => item.id === candidate.id);
}
