export function formatAuditTime(value) {
  if (!value) return "—";
  const raw = String(value);
  const match = raw.match(/(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})/);
  if (match) {
    const date = new Date(`${match[1]}T${match[2]}:00`);
    if (!Number.isNaN(date.getTime())) {
      return date.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    }
  }
  return raw.replace("T", " ").slice(0, 16);
}

export function initialsFromName(name) {
  const parts = String(name || "?")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

export function summarizeTimeline(timeline = []) {
  const authors = new Set();
  let changeFields = 0;
  for (const entry of timeline) {
    if (entry?.author) authors.add(entry.author);
    changeFields += (entry?.field_changes || []).length;
    if (entry?.body_text) changeFields += 1;
  }
  return {
    changeCount: timeline.length,
    fieldChangeCount: changeFields,
    userCount: authors.size,
    authors: [...authors],
  };
}

export function summarizeActivity(data) {
  const byModel = data?.by_model || [];
  const recordsChanged = byModel.reduce((sum, group) => sum + (group.records_changed || 0), 0);
  return {
    changeCount: data?.total_changes || 0,
    userCount: data?.user ? 1 : 0,
    authors: data?.user ? [data.user] : [],
    modelCount: byModel.length,
    recordsChanged,
  };
}

export function buildSummaryFromAuditData(auditData) {
  if (!auditData) return null;
  if (auditData.view === "timeline") {
    const stats = summarizeTimeline(auditData.timeline || []);
    return {
      view: "timeline",
      changeCount: auditData.changes_count ?? stats.changeCount,
      userCount: stats.userCount,
      authors: stats.authors,
      label: auditData.model
        ? `${auditData.model} #${auditData.record_id}`
        : "Record audit",
    };
  }
  if (auditData.view === "activity") {
    const stats = summarizeActivity(auditData);
    return {
      view: "activity",
      changeCount: stats.changeCount,
      userCount: stats.userCount,
      authors: stats.authors,
      label: auditData.user || "User activity",
    };
  }
  return null;
}

export const AUDIT_SUGGESTIONS = [
  "What changed today on Villa Maintenance No. 34",
  "Recent updates by user 4291",
  "Status changes on projects this week",
];
