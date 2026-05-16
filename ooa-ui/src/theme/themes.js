export const THEMES = {
  starlight: {
    name: "starlight",
    label: "STARLIGHT",
    colors: {
      bgBase: "#f4f7fc",
      textPrimary: "#1a1f3a",
      textSecondary: "#5a6378",
      textMuted: "rgba(26, 31, 58, 0.45)",
      gold: "#c9a84c",
      cyan: "#4ecdc4",
      coral: "#ff6b6b",
      royal: "#5b6fe6",
    },
    glass: {
      bg: "rgba(255, 255, 255, 0.55)",
      border: "rgba(255, 255, 255, 0.65)",
      shadow: "0 8px 32px rgba(31, 38, 135, 0.12)",
      innerGlow: "inset 0 1px 0 rgba(255,255,255,0.8)",
    },
    gradients: {
      app: "linear-gradient(135deg, #f4f7fc 0%, #e8edf7 45%, #f0e7f9 100%)",
      userBubble: "linear-gradient(135deg, #c9a84c, #a8873d)",
      orbA: "rgba(201, 168, 76, 0.18)",
      orbB: "rgba(78, 205, 196, 0.14)",
      orbC: "rgba(91, 111, 230, 0.12)",
    },
  },
  blackbat: {
    name: "blackbat",
    label: "BLACKBAT",
    colors: {
      bgBase: "#060b1a",
      textPrimary: "#e8eaf6",
      textSecondary: "rgba(232, 234, 246, 0.7)",
      textMuted: "rgba(232, 234, 246, 0.4)",
      gold: "#d4af37",
      cyan: "#4ecdc4",
      coral: "#ff6b6b",
      royal: "#8b5cf6",
    },
    glass: {
      bg: "rgba(255, 255, 255, 0.05)",
      border: "rgba(255, 255, 255, 0.08)",
      shadow: "0 8px 32px rgba(0, 0, 0, 0.5)",
      innerGlow: "inset 0 1px 0 rgba(255,255,255,0.1)",
    },
    gradients: {
      app: "radial-gradient(circle at top, #0a0f1e 0%, #060b1a 45%, #050714 100%)",
      userBubble: "linear-gradient(135deg, #d4af37, #a8873d)",
      orbA: "rgba(212, 175, 55, 0.12)",
      orbB: "rgba(78, 205, 196, 0.08)",
      orbC: "rgba(139, 92, 246, 0.1)",
    },
  },
};

export const DEFAULT_THEME = (() => {
  if (typeof window === "undefined") return "blackbat";
  const stored = localStorage.getItem("ooa_theme");
  if (stored && THEMES[stored]) return stored;
  return window.matchMedia?.("(prefers-color-scheme: light)").matches
    ? "starlight"
    : "blackbat";
})();

export function applyThemeVariables(theme) {
  if (typeof document === "undefined" || !theme) return;
  const root = document.documentElement;
  root.dataset.theme = theme.name;
  root.style.setProperty("--ooa-bg", theme.gradients.app);
  root.style.setProperty("--ooa-text", theme.colors.textPrimary);
  root.style.setProperty("--ooa-text-secondary", theme.colors.textSecondary);
  root.style.setProperty("--ooa-text-muted", theme.colors.textMuted);
  root.style.setProperty("--ooa-gold", theme.colors.gold);
  root.style.setProperty("--ooa-cyan", theme.colors.cyan);
  root.style.setProperty("--ooa-coral", theme.colors.coral);
  root.style.setProperty("--ooa-royal", theme.colors.royal);
  root.style.setProperty("--ooa-glass-bg", theme.glass.bg);
  root.style.setProperty("--ooa-glass-border", theme.glass.border);
  root.style.setProperty("--ooa-glass-shadow", theme.glass.shadow);
  root.style.setProperty("--ooa-glass-inner", theme.glass.innerGlow);
  root.style.setProperty("--ooa-user-bubble", theme.gradients.userBubble);
  root.style.setProperty("--ooa-orb-a", theme.gradients.orbA);
  root.style.setProperty("--ooa-orb-b", theme.gradients.orbB);
  root.style.setProperty("--ooa-orb-c", theme.gradients.orbC);
}
