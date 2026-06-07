import { useEffect, useRef, useState } from "react";
import { setAutoSkipSplash, setSplashThemePreference } from "./splashStorage";

function initials(name) {
  const parts = String(name || "U").trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] || ""}${parts[1][0] || ""}`.toUpperCase();
}

export default function TopBar({
  user,
  splashTheme,
  autoSkip,
  onThemeChange,
  onAutoSkipChange,
}) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const settingsRef = useRef(null);

  useEffect(() => {
    if (!settingsOpen) return undefined;
    const onPointer = (event) => {
      if (settingsRef.current && !settingsRef.current.contains(event.target)) {
        setSettingsOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointer);
    return () => document.removeEventListener("mousedown", onPointer);
  }, [settingsOpen]);

  const displayName = user?.userName || "User";
  const role = user?.roles?.[0] || "Finance";

  return (
    <header className="splash-topbar">
      <div className="splash-topbar__left">
        <button type="button" className="splash-topbar__profile" aria-label="Profile">
          <span className="splash-topbar__avatar" aria-hidden="true">
            {initials(displayName)}
          </span>
          <span className="splash-topbar__meta">
            <span className="splash-topbar__name">{displayName}</span>
            <span className="splash-topbar__role">{role}</span>
          </span>
        </button>
        <button
          type="button"
          className="splash-icon-btn"
          aria-label="Apps"
          title="Apps (coming soon)"
          disabled
        >
          ::
        </button>
      </div>

      <div className="splash-topbar__right">
        <button type="button" className="splash-icon-btn" aria-label="Search" title="Search">
          🔍
        </button>
        <button
          type="button"
          className="splash-icon-btn"
          aria-label="Notifications"
          title="Notifications"
        >
          🔔
        </button>
        <div ref={settingsRef} style={{ position: "relative" }}>
          <button
            type="button"
            className="splash-icon-btn"
            aria-label="Settings"
            aria-expanded={settingsOpen}
            onClick={() => setSettingsOpen((open) => !open)}
          >
            ⚙
          </button>
          {settingsOpen ? (
            <div className="splash-settings" role="menu">
              <span className="splash-settings__label">Splash theme</span>
              {[
                { id: "dark", label: "Dark (hero)" },
                { id: "light", label: "Light (cream)" },
                { id: "abstract", label: "Abstract minimal" },
              ].map((option) => (
                <label key={option.id} className="splash-settings__option">
                  <input
                    type="radio"
                    name="splash-theme"
                    checked={splashTheme === option.id}
                    onChange={() => {
                      setSplashThemePreference(option.id);
                      onThemeChange?.(option.id);
                    }}
                  />
                  {option.label}
                </label>
              ))}
              <label className="splash-settings__toggle">
                <input
                  type="checkbox"
                  checked={autoSkip}
                  onChange={(event) => {
                    setAutoSkipSplash(event.target.checked);
                    onAutoSkipChange?.(event.target.checked);
                  }}
                />
                Skip splash on launch
              </label>
            </div>
          ) : null}
        </div>
      </div>
    </header>
  );
}
