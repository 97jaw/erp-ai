import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { DEFAULT_THEME, THEMES, applyThemeVariables } from "./themes";

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [themeName, setThemeName] = useState(() => {
    const stored = localStorage.getItem("ooa_theme");
    return THEMES[stored] ? stored : DEFAULT_THEME;
  });

  const theme = THEMES[themeName] || THEMES.blackbat;

  useEffect(() => {
    applyThemeVariables(theme);
    localStorage.setItem("ooa_theme", theme.name);
  }, [theme]);

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
