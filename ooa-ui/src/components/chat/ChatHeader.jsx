import Logo from "../common/Logo";
import ThemeToggle from "../common/ThemeToggle";
import ProfileMenu from "./ProfileMenu";

export default function ChatHeader({
  user,
  onLogout,
  onToggleSidebar,
  soundEnabled,
  volume,
  onToggleSound,
  onVolumeChange,
}) {
  return (
    <header className="ooa-chat-header">
      <Logo />
      <div className="ooa-chat-header__actions">
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
