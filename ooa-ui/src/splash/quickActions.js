export const QUICK_ACTIONS = [
  { id: "pl", label: "P&L", query: "Show me profit and loss", icon: "📊" },
  { id: "projects", label: "Projects", query: "Show active projects", icon: "🏗" },
  { id: "cash", label: "Cash", query: "Show cash flow this month", icon: "💰" },
  { id: "reports", label: "Reports", query: "Generate monthly report", icon: "📄" },
  { id: "voice", label: "Voice", query: "", icon: "🎙", action: "voice" },
  { id: "more", label: "More", query: "What can you help me with today?", icon: "⋯" },
];

export const CAPABILITY_HINTS = {
  1: "Did you know? Ask in Arabic anytime.",
  2: "Generate PDFs by saying \"create report\".",
  3: "Drag any answer to Visualize for export.",
  4: "Voice queries work in both languages.",
  5: "Get email summaries via Outlook integration.",
  0: "Connect Outlook to unlock inbox insights.",
};

export function capabilityHintForToday() {
  return CAPABILITY_HINTS[new Date().getDay()] || CAPABILITY_HINTS[1];
}
