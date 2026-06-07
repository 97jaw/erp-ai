import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  IconBell,
  IconIntegration,
  IconLogout,
  IconSearch,
} from "../../components/common/MainIcons";
import ProfileMenu from "../../components/chat/ProfileMenu";
import MainThemeMenu from "./MainThemeMenu";
import { INTEGRATIONS } from "../integrations/integrationConfig";

function statusDotClass(status) {
  if (status === "connected") return "ooa-main-topbar__dot--connected";
  if (status === "error") return "ooa-main-topbar__dot--error";
  return "ooa-main-topbar__dot--idle";
}

export default function MainTopBar({
  user,
  onLogout,
  onClearConversation,
  soundEnabled,
  volume,
  onToggleSound,
  onVolumeChange,
  onOpenSearch,
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const [tooltip, setTooltip] = useState(null);
  const onIntegration = location.pathname.startsWith("/integrations");

  const showTooltip = (integration) => {
    const statusLabel =
      integration.status === "connected"
        ? "Connected"
        : integration.status === "error"
          ? "Disconnected"
          : "Not connected";
    setTooltip({ name: integration.name, status: statusLabel });
  };

  return (
    <header className="ooa-main-topbar" role="banner">
      <div className="ooa-main-topbar__group ooa-main-topbar__group--identity">
        <ProfileMenu
          user={user}
          soundEnabled={soundEnabled}
          volume={volume}
          onToggleSound={onToggleSound}
          onVolumeChange={onVolumeChange}
          onClearConversation={onClearConversation}
        />
        <button
          type="button"
          className="ooa-main-topbar__icon-btn"
          aria-label="Log out"
          title="Log out"
          onClick={onLogout}
        >
          <IconLogout />
        </button>
      </div>

      <div className="ooa-main-topbar__group ooa-main-topbar__group--integrations">
        {INTEGRATIONS.map((integration) => {
          const active = location.pathname === integration.path;
          return (
            <button
              key={integration.id}
              type="button"
              className={`ooa-main-topbar__integration${active ? " ooa-main-topbar__integration--active" : ""}`}
              aria-label={`${integration.name} integration`}
              aria-current={active ? "page" : undefined}
              onMouseEnter={() => showTooltip(integration)}
              onMouseLeave={() => setTooltip(null)}
              onFocus={() => showTooltip(integration)}
              onBlur={() => setTooltip(null)}
              onClick={() => navigate(integration.path)}
            >
              <span className="ooa-main-topbar__integration-icon" aria-hidden="true">
                <IconIntegration id={integration.id} />
              </span>
              <span
                className={`ooa-main-topbar__dot ${statusDotClass(integration.status)}`}
                aria-hidden="true"
              />
            </button>
          );
        })}
        {tooltip ? (
          <span className="ooa-main-topbar__tooltip" role="tooltip">
            {tooltip.name} · {tooltip.status}
          </span>
        ) : null}
      </div>

      <div className="ooa-main-topbar__group ooa-main-topbar__group--utility">
        <button
          type="button"
          className="ooa-main-topbar__icon-btn"
          aria-label="Search"
          title="Search"
          onClick={onOpenSearch}
        >
          <IconSearch />
        </button>
        <button
          type="button"
          className="ooa-main-topbar__icon-btn"
          aria-label="Notifications"
          title="Notifications"
        >
          <IconBell />
        </button>
        <MainThemeMenu />
        {onIntegration ? (
          <button
            type="button"
            className="ooa-main-topbar__back-chat"
            onClick={() => navigate("/")}
          >
            Back to Chat
          </button>
        ) : null}
      </div>
    </header>
  );
}
