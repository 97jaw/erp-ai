export const SHOWCASE_FEATURES = [
  {
    id: "financial",
    icon: "📊",
    title: "Financial Reports",
    subtitle: "P&L, Balance Sheet, Cash Flow",
    query: "Show profit and loss this month",
  },
  {
    id: "projects",
    icon: "🏗️",
    title: "Project Insights",
    subtitle: "Cost tracking, budget alerts",
    query: "Show active projects",
  },
  {
    id: "customers",
    icon: "👥",
    title: "Customer Analytics",
    subtitle: "Receivables, ageing analysis",
    query: "Who owes us money",
  },
  {
    id: "voice",
    icon: "🎤",
    title: "Voice Native",
    subtitle: "Speak in Arabic or English",
    query: "Show profit and loss this month",
  },
  {
    id: "pdf",
    icon: "📄",
    title: "PDF Reports",
    subtitle: "AI-designed beautiful exports",
    query: "Generate a PDF financial report for this month",
  },
  {
    id: "bilingual",
    icon: "🌐",
    title: "Arabic + English",
    subtitle: "Native multilingual",
    query: "الأرباح والخسائر لهذا الشهر",
  },
];

export const LIVE_SUGGESTION_TEMPLATES = [
  "Show profit and loss this month",
  "Show active projects",
  "Who owes us money",
  "Show trial balance",
  "Compare this month vs last month",
  "Generate a PDF financial report for this month",
  "الأرباح والخسائر لهذا الشهر",
];

export function filterLiveSuggestions(input, limit = 4) {
  const needle = (input || "").trim().toLowerCase();
  if (!needle) return LIVE_SUGGESTION_TEMPLATES.slice(0, limit);
  return LIVE_SUGGESTION_TEMPLATES
    .filter((item) => item.toLowerCase().includes(needle))
    .slice(0, limit);
}

export function formatQueryAge(timestamp) {
  if (!timestamp) return "Just now";
  const minutes = Math.max(1, Math.round((Date.now() - timestamp) / 60000));
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}
