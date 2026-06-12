import { apiFetch } from "../config/api";
import { normalizeVisualization, resolveVisualizationLevel } from "../utils/chat";

function embeddedRowCount(viz) {
  const data = viz?.data || {};
  const allRows = data.all_rows || data.detail_table?.rows || [];
  if (allRows.length) return allRows.length;
  return (data.rows || []).length;
}

function needsServerFullExport(viz) {
  if (!viz?.query_id) return false;
  const total = viz.total_records ?? 0;
  if (!total) return false;
  return embeddedRowCount(viz) < total;
}

/**
 * Expand visualization to full disclosure level for Visualize.
 * Fetches all paginated rows from the server when only a page is cached client-side.
 */
export async function prepareVisualizationForVisualize(viz) {
  const normalized = normalizeVisualization(viz);
  if (!normalized) return null;

  if (needsServerFullExport(normalized)) {
    try {
      const payload = await apiFetch("/query/full", {
        method: "POST",
        body: JSON.stringify({ query_id: normalized.query_id }),
      });
      const data = normalized.data || {};
      const merged = {
        ...normalized,
        data: {
          ...data,
          headers: payload.headers || data.headers || data.detail_table?.headers,
          rows: payload.rows || [],
          all_rows: payload.rows || [],
        },
        total_records: payload.total_records ?? payload.rows?.length ?? normalized.total_records,
        shown_records: payload.total_records ?? payload.rows?.length,
        level: "full",
      };
      return resolveVisualizationLevel(merged, "full");
    } catch {
      /* fall through to client-side expansion */
    }
  }

  return resolveVisualizationLevel(normalized, "full");
}

/** Sync best-effort expansion when all_rows are already embedded in the payload. */
export function prepareVisualizationForVisualizeSync(viz) {
  const normalized = normalizeVisualization(viz);
  if (!normalized) return null;
  return resolveVisualizationLevel(normalized, "full");
}
