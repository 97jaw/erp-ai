import { notifyThemeSync, syncAppThemeFromSplash } from "../theme/syncAppTheme";
import { normalizeStoredTheme } from "./themes/splashThemes";

const KEYS = {
  hasVisited: "ooa_has_visited",
  autoSkip: "ooa_auto_skip_splash",
  lastAction: "ooa_last_splash_action",
  pendingQuery: "ooa_splash_query",
  splashTheme: "ooa_splash_theme",
};

export function shouldAutoSkipSplash() {
  return localStorage.getItem(KEYS.autoSkip) === "true";
}

export function markSplashVisited(action = "skipped") {
  localStorage.setItem(KEYS.hasVisited, "true");
  localStorage.setItem(KEYS.lastAction, action);
}

export function setAutoSkipSplash(enabled) {
  localStorage.setItem(KEYS.autoSkip, enabled ? "true" : "false");
}

export function isFirstSplashVisit() {
  return localStorage.getItem(KEYS.hasVisited) !== "true";
}

export function stashSplashQuery(query) {
  if (query?.trim()) {
    localStorage.setItem(KEYS.pendingQuery, query.trim());
  }
}

export function consumeSplashQuery() {
  const value = localStorage.getItem(KEYS.pendingQuery);
  if (value) localStorage.removeItem(KEYS.pendingQuery);
  return value || "";
}

/** Stored preference: sky | dark | abstract | auto */
export function getSplashThemePreference() {
  const stored = localStorage.getItem(KEYS.splashTheme);
  return normalizeStoredTheme(stored || "abstract");
}

export function setSplashThemePreference(theme) {
  localStorage.setItem(KEYS.splashTheme, theme);
  syncAppThemeFromSplash();
  notifyThemeSync();
}
