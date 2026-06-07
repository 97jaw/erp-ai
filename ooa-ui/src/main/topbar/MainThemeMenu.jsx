import { useEffect, useRef, useState } from "react";
import { IconSun } from "../../components/common/MainIcons";
import {
  getSplashThemePreference,
  setSplashThemePreference,
} from "../../splash/splashStorage";
import { SPLASH_THEME_OPTIONS } from "../../splash/themes/splashThemes";
import { THEME_SYNC_EVENT } from "../../theme/syncAppTheme";

export default function MainThemeMenu() {
  const [open, setOpen] = useState(false);
  const [themePref, setThemePref] = useState(getSplashThemePreference);
  const wrapRef = useRef(null);

  useEffect(() => {
    const onSync = () => setThemePref(getSplashThemePreference());
    window.addEventListener(THEME_SYNC_EVENT, onSync);
    return () => window.removeEventListener(THEME_SYNC_EVENT, onSync);
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    const onPointer = (event) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    const onKey = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const selectTheme = (id) => {
    setSplashThemePreference(id);
    setThemePref(id);
    setOpen(false);
  };

  return (
    <div ref={wrapRef} className="ooa-main-theme-menu">
      <button
        type="button"
        className="ooa-main-topbar__icon-btn"
        aria-label="Theme"
        aria-expanded={open}
        aria-haspopup="menu"
        title="Theme"
        onClick={() => setOpen((value) => !value)}
      >
        <IconSun />
      </button>
      {open ? (
        <div className="ooa-main-theme-menu__panel" role="menu">
          <span className="ooa-main-theme-menu__label">Theme</span>
          {SPLASH_THEME_OPTIONS.map((option) => (
            <label key={option.id} className="ooa-main-theme-menu__option">
              <input
                type="radio"
                name="main-theme"
                checked={themePref === option.id}
                onChange={() => selectTheme(option.id)}
              />
              {option.label}
            </label>
          ))}
        </div>
      ) : null}
    </div>
  );
}
