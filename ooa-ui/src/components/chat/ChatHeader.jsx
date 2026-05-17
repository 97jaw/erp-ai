import { Link } from "react-router-dom";
import Logo from "../common/Logo";
import ThemeToggle from "../common/ThemeToggle";
import ProfileMenu from "./ProfileMenu";
import { readStoredAuth } from "../../config/api";

export default function ChatHeader({
  user,
  onLogout,
  onToggleSidebar,
  soundEnabled,
  volume,
  onToggleSound,
  onVolumeChange,
}) {
  const auth = readStoredAuth();
  const showAdmin =
    auth?.permissions?.some((p) => p.startsWith("admin.")) ||
    (auth?.roles || []).includes("super_admin");

  return (
    <header className="ooa-chat-header">
      <Logo />
      <div className="ooa-chat-header__actions">
        {showAdmin ? (
          <Link
            to="/admin"
            className="ooa-glass-button"
            style={{ textDecoration: "none", display: "inline-flex", alignItems: "center" }}
          >
            Admin
          </Link>
        ) : null}
        <ThemeToggle />
        <ProfileMenu
          user={user}
          soundEnabled={soundEnabled}
          volume={volume}
          onToggleSound={onToggleSound}
          onVolumeChange={onVolumeChange}
        />
        <button
          type="button"
          className="ooa-glass-button ooa-chat-header__menu"
          onClick={onToggleSidebar}
          aria-label="Open quick actions"
        >
          Menu
        </button>
        <button type="button" className="ooa-glass-button" onClick={onLogout}>
          Logout
        </button>
        <span className="ooa-status-pill">Live</span>
      </div>
    </header>
  );
}
