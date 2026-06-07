import { useEffect, useRef, useState } from "react";
import ProfileBlock from "./ProfileBlock";
import { SPLASH_THEME_OPTIONS } from "./themes/splashThemes";
import { setAutoSkipSplash, setSplashThemePreference } from "./splashStorage";

export default function SplashHeader({
  user,
  isLoggedIn,
  revealHeader,
  awaitingReveal = false,
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

  return (
    <header className="splash-header">
      <div className="splash-header__left">
        {isLoggedIn ? (
          <ProfileBlock
            user={user}
            isLoggedIn
            className={
              revealHeader
                ? "splash-pop-in splash-pop-in--delay-2"
                : awaitingReveal
                  ? "splash-await-reveal"
                  : ""
            }
          />
        ) : (
          <span className="splash-header__spacer" aria-hidden="true" />
        )}
        {isLoggedIn ? (
          <button
            type="button"
            className={`splash-icon-btn${
              revealHeader
                ? " splash-pop-in splash-pop-in--delay-3"
                : awaitingReveal
                  ? " splash-await-reveal"
                  : ""
            }`}
            aria-label="Apps"
            title="Apps (coming soon)"
            disabled
          >
            ::
          </button>
        ) : null}
      </div>

      <div className="splash-header__right">
        {isLoggedIn ? (
          <>
            <button
              type="button"
              className={`splash-icon-btn${
                revealHeader
                  ? " splash-pop-in splash-pop-in--delay-4"
                  : awaitingReveal
                    ? " splash-await-reveal"
                    : ""
              }`}
              aria-label="Search"
              title="Search"
            >
              🔍
            </button>
            <button
              type="button"
              className={`splash-icon-btn splash-icon-btn--badge${
                revealHeader
                  ? " splash-pop-in splash-pop-in--delay-5"
                  : awaitingReveal
                    ? " splash-await-reveal"
                    : ""
              }`}
              aria-label="Notifications"
              title="Notifications"
            >
              🔔
            </button>
          </>
        ) : null}
        <div ref={settingsRef} className="splash-header__settings-wrap">
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
              <span className="splash-settings__label">Theme</span>
              {SPLASH_THEME_OPTIONS.map((option) => (
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
