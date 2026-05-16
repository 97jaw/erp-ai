import { useEffect, useRef, useState } from "react";
import GlassButton from "../glass/GlassButton";

export default function ProfileMenu({
  user,
  soundEnabled,
  volume,
  onToggleSound,
  onVolumeChange,
}) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    const onPointerDown = (event) => {
      if (!menuRef.current?.contains(event.target)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  return (
    <div className="ooa-profile-menu" ref={menuRef}>
      <GlassButton
        className="ooa-profile-menu__trigger"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
        aria-haspopup="menu"
      >
        Profile
      </GlassButton>

      {open ? (
        <div className="ooa-profile-menu__panel" role="menu">
          <div className="ooa-profile-menu__name">{user?.userName || "Workspace user"}</div>
          {user?.fileId ? (
            <div className="ooa-profile-menu__meta">File ID {user.fileId}</div>
          ) : null}

          <label className="ooa-profile-menu__row">
            <input
              type="checkbox"
              checked={soundEnabled}
              onChange={() => onToggleSound()}
            />
            <span>UI sound effects</span>
          </label>

          <label className="ooa-profile-menu__volume">
            <span>Volume</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={volume}
              onChange={(event) => onVolumeChange(Number(event.target.value))}
              disabled={!soundEnabled}
            />
          </label>
        </div>
      ) : null}
    </div>
  );
}
