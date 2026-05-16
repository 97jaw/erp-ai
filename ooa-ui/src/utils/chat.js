export const API_BASE = "http://localhost:8000";

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

export const isArabic = (text = "") => /[\u0600-\u06FF]/.test(text);

export const sessionId = () => Math.random().toString(36).slice(2);

export const getStoredSessionId = () => {
  let id = localStorage.getItem("ooa_session_id");
  if (!id) {
    id = sessionId();
    localStorage.setItem("ooa_session_id", id);
  }
  return id;
};

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
  } catch (error) {}
  return fallback;
};

export const decodeHeader = (encodedHeader, plainHeader, fallback) => {
  if (encodedHeader) {
    try {
      const bytes = Uint8Array.from(atob(encodedHeader), (char) => char.charCodeAt(0));
      return new TextDecoder("utf-8").decode(bytes);
    } catch (error) {}
  }
  return plainHeader || fallback;
};

export const stripVisualization = (text = "") => {
  let cleaned = text || "";
  cleaned = cleaned.replace(/<viz-hint>\s*[^<]+?\s*<\/viz-hint>/gi, "");
  const tagStart = cleaned.indexOf("<visualization>");
  if (tagStart >= 0) {
    cleaned = cleaned.slice(0, tagStart);
  }
  cleaned = cleaned.replace(/<\/visualization>\s*/g, "");
  cleaned = cleaned.replace(/\{\s*"visual_type"[\s\S]*?(?:\}\s*<\/visualization>|\}\s*$)/g, "");
  cleaned = cleaned.replace(/(?:\n|^)\s*(?:\{\s*)?"visual_type"\s*:[\s\S]*$/i, "");
  cleaned = cleaned.replace(/\n\*\*Suggestions:\*\*[\s\S]*$/i, "");
  return cleaned.trim();
};

export const normalizeSuggestion = (text = "") =>
  text
    .replace(/^\d+\.\s*/, "")
    .replace(/\*\*/g, "")
    .replace(/\s+/g, " ")
    .trim();

export const normalizeVisualization = (viz) => {
  if (!viz || typeof viz !== "object") return null;
  const normalized = { ...viz };
  const data = normalized.data;
  if (data && typeof data === "object") {
    if (!normalized.kpis && data.kpis && typeof data.kpis === "object") {
      normalized.kpis = data.kpis;
    }
    ["date_from", "date_to", "report_name", "label"].forEach((key) => {
      if (normalized[key] == null && data[key] != null) {
        normalized[key] = data[key];
      }
    });
  }
  return normalized;
};

export const hasRenderableVisualization = (viz) => {
  const normalized = normalizeVisualization(viz);
  if (!normalized) return false;
  const { visual_type: visualType } = normalized;
  if (visualType === "KPI_CARD") {
    return normalized.label != null && normalized.value != null;
  }
  if (visualType === "DATA_TABLE") {
    return Boolean(normalized.data?.rows?.length);
  }
  if (visualType === "FINANCIAL_REPORT") {
    const kpis = normalized.kpis;
    if (!kpis || typeof kpis !== "object") return false;
    return ["total_income", "total_expense", "net_profit", "margin", "total_cost"].some(
      (key) => Object.prototype.hasOwnProperty.call(kpis, key)
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
