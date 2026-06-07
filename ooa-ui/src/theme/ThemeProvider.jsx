import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { DEFAULT_THEME, THEMES, applyThemeVariables } from "./themes";
import { THEME_SYNC_EVENT, syncAppThemeFromSplash } from "./syncAppTheme";

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [themeName, setThemeName] = useState(() => {
    const synced = syncAppThemeFromSplash();
    if (THEMES[synced]) return synced;
    const stored = localStorage.getItem("ooa_theme");
    return THEMES[stored] ? stored : DEFAULT_THEME;
  });

  const theme = THEMES[themeName] || THEMES.abstract;

  useEffect(() => {
    applyThemeVariables(theme);
    localStorage.setItem("ooa_theme", theme.name);
  }, [theme]);

  useEffect(() => {
    const onSync = () => {
      const synced = syncAppThemeFromSplash();
      if (THEMES[synced]) setThemeName(synced);
    };
    window.addEventListener(THEME_SYNC_EVENT, onSync);
    return () => window.removeEventListener(THEME_SYNC_EVENT, onSync);
  }, []);

  const value = useMemo(
    () => ({
      theme,
      themeName,
      setThemeName,
      toggleTheme: () =>
        setThemeName((current) => (current === "blackbat" ? "starlight" : "blackbat")),
    }),
    [theme, themeName]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return context;
}
