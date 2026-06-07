import { getSplashThemePreference } from "../splash/splashStorage";
import { resolveSplashTheme } from "../splash/themes/splashThemes";
import { applyThemeVariables, THEMES } from "./themes";

export const SPLASH_TO_APP_THEME = {
  sky: "starlight",
  abstract: "abstract",
  dark: "blackbat",
};

export const THEME_SYNC_EVENT = "ooa-theme-sync";

/** Map splash preference → main app theme and apply CSS variables. */
export function syncAppThemeFromSplash() {
  const splash = resolveSplashTheme(getSplashThemePreference());
  const appThemeName = SPLASH_TO_APP_THEME[splash] || "abstract";
  const theme = THEMES[appThemeName] || THEMES.abstract;
  applyThemeVariables(theme);
  localStorage.setItem("ooa_theme", appThemeName);
  return appThemeName;
}

export function notifyThemeSync() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(THEME_SYNC_EVENT));
  }
}
