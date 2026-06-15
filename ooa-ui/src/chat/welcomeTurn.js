import { buildWelcomeMessage } from "../utils/chat";
import { SHOWCASE_FEATURES } from "../utils/layoutContent";

export const WELCOME_TURN_ID = "ooa-welcome-turn";

const TOP_MENU_OPTIONS = [
  { id: "financial", label: "Financial Reports", icon: "📊" },
  { id: "projects", label: "Projects & Costs", icon: "🏗️" },
  { id: "documents", label: "Documents & Files", icon: "📎" },
  { id: "hr", label: "HR & Employees", icon: "👥" },
  { id: "payroll", label: "Payroll & Payslips", icon: "💰" },
  { id: "procurement", label: "Procurement & LPOs", icon: "📋" },
  { id: "fleet", label: "Fleet & Vehicles", icon: "🚗" },
  { id: "receivables", label: "Receivables & AR", icon: "📈" },
  { id: "search", label: "Search / Ask Anything", icon: "🔍" },
];

export function buildWelcomeTurn(user) {
  const intro = buildWelcomeMessage(user).split("\n\n")[0].trim();
  const prompt = "What would you like to explore?";
  return {
    id: WELCOME_TURN_ID,
    question: "",
    isWelcome: true,
    createdAt: Date.now(),
    status: "complete",
    response: {
      text: intro,
      uiBlocks: [
        {
          type: "pill_select",
          prompt,
          options: TOP_MENU_OPTIONS,
          mode: "single",
          allow_typed_input: true,
        },
      ],
      suggestions: SHOWCASE_FEATURES.slice(0, 3).map((item) => item.query),
      suggestionDetails: null,
      suggestionMeta: null,
      visualization: null,
    },
  };
}

export function withWelcomeTurn(queries = [], user) {
  if (!user) return queries;
  if (queries.some((query) => query.isWelcome || query.id === WELCOME_TURN_ID)) {
    return queries;
  }
  if (queries.length > 0) return queries;
  return [buildWelcomeTurn(user)];
}

export function ensureWelcomeOnEmpty(queries, user) {
  if (queries.length > 0) return queries;
  return withWelcomeTurn([], user);
}
