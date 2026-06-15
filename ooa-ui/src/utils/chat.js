export { API_BASE, resolveApiBase } from "../config/api";

export const QUICK_ACTIONS = [
  { icon: "📊", label: "P&L Report", query: "Show profit and loss this month" },
  { icon: "🏗️", label: "Projects", query: "Show active projects" },
  { icon: "👥", label: "Receivables", query: "Who owes us money" },
  { icon: "📈", label: "Trial Balance", query: "Show trial balance" },
  { icon: "💰", label: "Expenses", query: "Show this month expenses" },
  { icon: "📅", label: "Compare", query: "Compare this month vs last month" },
];

export const WELCOME_CARDS = [
  { icon: "📊", title: "P&L Report", subtitle: "This month summary", query: "Show profit and loss this month" },
  { icon: "🏗️", title: "Project Cost", subtitle: "Specific project", query: "Total cost for a project" },
  { icon: "👥", title: "Receivables", subtitle: "Who owes us money", query: "Who owes us money" },
  { icon: "📅", title: "Compare", subtitle: "Period comparison", query: "Compare this month vs last month" },
];

const ARABIC_RE = /[\u0600-\u06FF]/g;
const LATIN_RE = /[a-zA-Z]/g;

export const isArabic = (text = "") => ARABIC_RE.test(text);

/** Per-paragraph direction for mixed Arabic/English (Bug 7). */
export const detectTextDirection = (text = "", { prefer = "ltr" } = {}) => {
  const arabicChars = (text.match(ARABIC_RE) || []).length;
  const latinChars = (text.match(LATIN_RE) || []).length;
  if (arabicChars === 0) return "ltr";
  if (latinChars === 0) return "rtl";
  const letterTotal = arabicChars + latinChars;
  if (arabicChars / letterTotal >= 0.45) return "rtl";
  return prefer === "rtl" ? "rtl" : "ltr";
};

export const sessionId = () => Math.random().toString(36).slice(2);

const CHAT_THREAD_KEY = "ooa_chat_thread_id";

/**
 * Stable conversation key for backend history (survives re-login / new JWT).
 * Auth token is sent separately via Authorization header.
 */
export const getChatThreadId = () => {
  let id = localStorage.getItem(CHAT_THREAD_KEY);
  if (!id) {
    id = `thread_${crypto.randomUUID?.() || sessionId()}`;
    localStorage.setItem(CHAT_THREAD_KEY, id);
  }
  return id;
};

/** Start a fresh conversation thread (Clear conversation). */
export const rotateChatThreadId = () => {
  const id = `thread_${crypto.randomUUID?.() || sessionId()}`;
  localStorage.setItem(CHAT_THREAD_KEY, id);
  return id;
};

/** Resume a saved server conversation thread. */
export const setChatThreadId = (threadId) => {
  if (threadId) {
    localStorage.setItem(CHAT_THREAD_KEY, threadId);
  }
};

/** @deprecated Use getChatThreadId for chat API session_id. */
export const getStoredSessionId = () => getChatThreadId();

/** @deprecated Use rotateChatThreadId. */
export const rotateStoredSessionId = () => rotateChatThreadId();

export const buildWelcomeMessage = (user) => {
  const name = user?.userName?.trim();
  if (!name) {
    return "مرحباً! أنا مساعدك الذكي لنظام أودو. يمكنني مساعدتك في التقارير المالية، تكاليف المشاريع، والبحث في قاعدة البيانات.\n\nHello! I'm your Odoo AI assistant. Ask me anything about financials, projects, or your data.";
  }

  const intro = user?.welcomeMessage?.trim()
    || "I'm your Odoo AI assistant. Ask me anything about financials, projects, or your data.";

  return `Welcome back, ${name}!\n\n${intro}\n\nمرحباً ${name}! أنا مساعدك الذكي لنظام أودو.`;
};

export const getRecordingMimeType = () => {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
    "audio/ogg",
  ];
  return candidates.find((type) => window.MediaRecorder?.isTypeSupported(type)) || "";
};

export const recordingExtension = (mimeType = "") => {
  if (mimeType.includes("mp4")) return "m4a";
  if (mimeType.includes("ogg")) return "ogg";
  return "webm";
};

export const parseApiError = async (res, fallback) => {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail)) {
      return body.detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
    }
  } catch (error) {
    // ignore
  }
  return fallback;
};

export const decodeHeader = (encodedHeader, plainHeader, fallback) => {
  if (encodedHeader) {
    try {
      const bytes = Uint8Array.from(atob(encodedHeader), (char) => char.charCodeAt(0));
      return new TextDecoder("utf-8").decode(bytes);
    } catch (error) {
      // ignore
    }
  }
  return plainHeader || fallback;
};

/** Strip visualization / clarify markup from assistant text (Bug 1). */
export const stripVisualization = (text = "") => {
  let cleaned = String(text || "");

  cleaned = cleaned.replace(/<visualization>[\s\S]*?<\/visualization>/gi, "");
  cleaned = cleaned.replace(/<viz-hint>[\s\S]*?<\/viz-hint>/gi, "");
  cleaned = cleaned.replace(/<clarify>[\s\S]*?<\/clarify>/gi, "");

  const tagStart = cleaned.indexOf("<visualization>");
  if (tagStart >= 0) {
    cleaned = cleaned.slice(0, tagStart);
  }

  cleaned = cleaned.replace(/<\/visualization>\s*/gi, "");
  cleaned = cleaned.replace(/<\/viz-hint>\s*/gi, "");
  cleaned = cleaned.replace(/<\/clarify>\s*/gi, "");

  cleaned = cleaned.replace(/\{\s*"visual_type"[\s\S]*?(?:\}\s*<\/visualization>|\}\s*$)/gi, "");
  cleaned = cleaned.replace(/(?:\n|^)\s*(?:\{\s*)?"visual_type"\s*:[\s\S]*$/i, "");

  cleaned = cleaned.replace(/\n_Fetching [^_\n]+_\.\.\._\n/g, "");
  cleaned = cleaned.replace(/\n\*\*Suggestions:\*\*[\s\S]*$/i, "");
  cleaned = cleaned.replace(/(?:^|\n)\s*Let me (?:try|get|fetch|search|look|check)[^\n]*/gi, "");
  cleaned = cleaned.replace(/\n{3,}/g, "\n\n");
  cleaned = cleaned.replace(/\n{2,}/g, "\n");

  return cleaned.trim();
};

/** Humanize raw Odoo field syntax in visible text (Bug 2). */
export const humanizeOutput = (text = "") => {
  if (!text) return "";
  let out = String(text);
  out = out.replace(/\b(\w+):sum\b/gi, "$1");
  out = out.replace(/\b(\w+):count\b/gi, "$1");
  out = out.replace(/\b(\w+):avg\b/gi, "$1");
  out = out.replace(/partner_id\[(\d+),\s*['"]([^'"]+)['"]\]/gi, "$2");
  out = out.replace(/\[(\d+),\s*['"]([^'"]+)['"]\]/g, "$2");
  return out;
};

export const humanizeLabel = (label = "") => {
  let text = humanizeOutput(String(label));
  text = text.replace(/_/g, " ");
  text = text.replace(/\b\w/g, (char) => char.toUpperCase());
  return text.trim();
};

export const normalizeSuggestion = (text = "") =>
  text
    .replace(/^\d+\.\s*/, "")
    .replace(/\*\*/g, "")
    .replace(/\s+/g, " ")
    .trim();

export const formatDateRangeBadge = (dateFrom, dateTo, { defaulted = false } = {}) => {
  if (!dateFrom && !dateTo) return null;
  const from = dateFrom ? new Date(`${dateFrom}T00:00:00`) : null;
  const to = dateTo ? new Date(`${dateTo}T00:00:00`) : null;
  const fmt = (d) => d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  let label = "";
  if (from && to) {
    const days = Math.max(1, Math.round((to - from) / 86400000));
    label = `${fmt(from)} – ${fmt(to)} (${days} days)`;
  } else if (from) {
    label = `From ${fmt(from)}`;
  } else if (to) {
    label = `Until ${fmt(to)}`;
  }
  if (defaulted) {
    label = `${label} · default period`;
  }
  return label;
};

export const DISCLOSURE_LEVELS = ["summary", "standard", "full"];
export const STANDARD_PAGE_SIZE = 20;

export const normalizeVisualization = (viz) => {
  if (!viz || typeof viz !== "object") return null;
  const normalized = { ...viz };
  const data = normalized.data;
  if (data && typeof data === "object") {
    if (!normalized.kpis && data.kpis && typeof data.kpis === "object") {
      normalized.kpis = data.kpis;
    }
    [
      "date_from",
      "date_to",
      "report_name",
      "label",
      "date_was_defaulted",
      "level",
      "total_records",
      "shown_records",
      "can_expand",
      "expand_label",
      "page_size",
      "query_id",
    ].forEach((key) => {
      if (normalized[key] == null && data[key] != null) {
        normalized[key] = data[key];
      }
    });
  }
  return normalized;
};

export const supportsProgressiveDisclosure = (viz) => {
  const type = viz?.visual_type;
  return type === "FINANCIAL_REPORT" || type === "DATA_TABLE" || type === "GROUPED_TABLE";
};

/** Client-side level switch using rows embedded by the gateway (Phase 3). */
export const resolveVisualizationLevel = (viz, level = "summary") => {
  const base = normalizeVisualization(viz);
  if (!base || !supportsProgressiveDisclosure(base)) {
    return base;
  }

  const resolved = { ...base, level };
  const data = { ...(resolved.data || {}) };
  const pageSize = resolved.page_size || STANDARD_PAGE_SIZE;
  const detailRows = data.all_rows
    || data.detail_table?.rows
    || [];
  const allGroups = data.all_groups || data.groups || [];

  if (resolved.visual_type === "FINANCIAL_REPORT") {
    if (level === "summary") {
      data.rows = [];
    } else if (level === "standard") {
      data.headers = data.detail_table?.headers || data.headers;
      data.rows = detailRows.slice(0, pageSize);
      resolved.shown_records = data.rows.length;
    } else {
      data.headers = data.detail_table?.headers || data.headers;
      data.rows = detailRows;
      resolved.shown_records = detailRows.length;
    }
    resolved.total_records = resolved.total_records ?? detailRows.length;
    resolved.can_expand = detailRows.length > (level === "summary" ? 0 : pageSize);
  }

  if (resolved.visual_type === "DATA_TABLE") {
    const allRows = data.all_rows || data.rows || [];
    if (level === "summary") {
      data.rows = [];
    } else if (level === "standard") {
      data.rows = allRows.slice(0, pageSize);
      resolved.shown_records = data.rows.length;
    } else {
      data.rows = allRows;
      resolved.shown_records = allRows.length;
    }
    resolved.total_records = resolved.total_records ?? allRows.length;
    resolved.can_expand = allRows.length > pageSize;
  }

  if (resolved.visual_type === "GROUPED_TABLE") {
    if (level === "summary") {
      data.groups = allGroups.slice(0, 5);
    } else if (level === "standard") {
      data.groups = allGroups.slice(0, pageSize);
      resolved.shown_records = data.groups.length;
    } else {
      data.groups = allGroups;
      resolved.shown_records = allGroups.length;
    }
    resolved.total_records = resolved.total_records ?? allGroups.length;
    resolved.can_expand = allGroups.length > pageSize;
  }

  resolved.data = data;
  return resolved;
};

export const hasRenderableVisualization = (viz) => {
  const normalized = normalizeVisualization(viz);
  if (!normalized) return false;
  const { visual_type: visualType } = normalized;
  if (visualType === "KPI_CARD") {
    return normalized.label != null && normalized.value != null;
  }
  if (visualType === "DATA_TABLE") {
    if (normalized.level === "summary") {
      return Boolean(
        normalized.data?.summary_chart
        || normalized.can_expand
        || normalized.total_records,
      );
    }
    return Boolean(normalized.data?.rows?.length);
  }
  if (visualType === "FINANCIAL_REPORT") {
    const kpis = normalized.kpis;
    if (!kpis || typeof kpis !== "object") return false;
    return ["total_income", "total_expense", "net_profit", "margin", "total_cost"].some(
      (key) => Object.prototype.hasOwnProperty.call(kpis, key),
    );
  }
  if (visualType === "BAR_CHART" || visualType === "LINE_CHART") {
    const chartData = normalized.data;
    if (!chartData || typeof chartData !== "object") return false;
    if (Array.isArray(chartData.rows) && chartData.rows.length) return true;
    if (Array.isArray(chartData.labels) && chartData.labels.length) return true;
    if (Array.isArray(chartData.values) && chartData.values.length) return true;
    return Boolean(chartData.series?.[0]?.values?.length);
  }
  if (visualType === "PDF_REPORT") {
    return Boolean(normalized.data?.pdf_url);
  }
  if (visualType === "GROUPED_TABLE") {
    const groups = normalized.data?.groups || normalized.groups;
    return Array.isArray(groups) && groups.length > 0;
  }
  if (visualType === "PROJECT_EXPENSE_SUMMARY") {
    return Boolean(normalized.kpis?.wo_amount);
  }
  if (visualType === "PROJECT_EXPENSE_BREAKDOWN") {
    return Array.isArray(normalized.groups) && normalized.groups.length > 0;
  }
  if (visualType === "PROJECT_EXPENSE_COMPARISON") {
    return Array.isArray(normalized.projects) && normalized.projects.length >= 2;
  }
  if (visualType === "FILE_LIST") {
    const files = normalized.data?.files;
    return Array.isArray(files) && files.length > 0;
  }
  return false;
};

export const extractHistory = (messages, limit = 5) => {
  const seen = new Set();
  const items = [];
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.role !== "user") continue;
    const text = (message.text || "").replace(/^🎤\s*/, "").trim();
    if (!text || seen.has(text)) continue;
    seen.add(text);
    items.push(text);
    if (items.length >= limit) break;
  }
  return items;
};
