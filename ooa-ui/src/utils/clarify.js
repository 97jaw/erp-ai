import { isArabic } from "./chat";

export function buildClarificationQuery(originalQuery, option) {
  const base = String(originalQuery || "").trim();
  if (option?.action === "confirm_entity") {
    return base;
  }
  if (option?.action === "search_broader_entity") {
    const term = String(option.search_term || "").trim();
    if (!term) return base;
    return `show all projects containing ${term}`;
  }
  if (option?.action === "try_different_name") {
    return base;
  }
  const suffix = String(option?.query_suffix || "").trim();
  if (!suffix) return base;
  if (base.toLowerCase().includes(suffix.toLowerCase())) return base;
  return `${base}${suffix}`;
}

export function buildConfirmedEntities(option) {
  if (option?.action !== "confirm_entity" || !option?.entity_id) {
    return [];
  }
  return [{
    type: option.entity_type || "project",
    id: Number(option.entity_id),
    name: option.label || null,
  }];
}

export function clarificationQuestion(clarification) {
  if (!clarification) return "";
  if (isArabic(clarification.question || "")) {
    return clarification.question_ar || clarification.question || "";
  }
  return clarification.question || clarification.question_ar || "";
}

export function clarificationLabel(option, clarification) {
  if (!option) return "";
  const rtl = isArabic(clarification?.question || "");
  return rtl ? (option.label_ar || option.label) : (option.label || option.label_ar);
}
