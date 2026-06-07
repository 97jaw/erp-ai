/** Splash v2 themes — Sky Blue (light), Dark, Abstract. See SPLASH_SCREEN_PLAN_V2.md */

export const SPLASH_THEMES = {
  sky: {
    id: "sky",
    label: "Sky Blue (Light)",
    className: "splash-screen--sky",
  },
  dark: {
    id: "dark",
    label: "Dark",
    className: "splash-screen--dark",
  },
  abstract: {
    id: "abstract",
    label: "Abstract",
    className: "splash-screen--abstract",
  },
};

export const SPLASH_THEME_OPTIONS = [
  { id: "sky", label: "Sky Blue (Light)" },
  { id: "dark", label: "Dark" },
  { id: "abstract", label: "Abstract" },
  { id: "auto", label: "Auto (system)" },
];

export function normalizeStoredTheme(stored) {
  if (!stored) return "abstract";
  if (stored === "light") return "sky";
  if (stored === "sky" || stored === "dark" || stored === "abstract" || stored === "auto") {
    return stored;
  }
  return "abstract";
}

export function resolveSplashTheme(preference) {
  const normalized = normalizeStoredTheme(preference);
  if (normalized !== "auto") return normalized;
  if (typeof window === "undefined") return "abstract";
  return window.matchMedia?.("(prefers-color-scheme: light)")?.matches ? "sky" : "abstract";
}

export function splashThemeClass(preference) {
  const resolved = resolveSplashTheme(preference);
  return SPLASH_THEMES[resolved]?.className || "splash-screen--dark";
}
