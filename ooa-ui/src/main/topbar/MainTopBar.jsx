import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  IconAudit,
  IconBell,
  IconChats,
  IconDashboard,
  IconIntegration,
  IconLogout,
  IconNewChat,
  IconSearch,
  IconVisualize,
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
  onNewChat,
  onOpenChats,
  soundEnabled,
  volume,
  onToggleSound,
  onVolumeChange,
  onOpenSearch,
  mainView = "chat",
  visualizeOpen = false,
  onOpenAudit,
  onToggleVisualize,
  onBuildDashboard,
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
        {onOpenAudit ? (
          <button
            type="button"
            className={`ooa-main-topbar__ai-btn${
              mainView === "audit" ? " ooa-main-topbar__ai-btn--active" : ""
            } ooa-main-topbar__ai-btn--audit`}
            aria-label="Audit"
            title="Audit — change history & activity"
            aria-pressed={mainView === "audit"}
            onClick={onOpenAudit}
          >
            <IconAudit size={18} />
            <span className="ooa-main-topbar__btn-label">Audit</span>
          </button>
        ) : null}
        {onToggleVisualize ? (
          <button
            type="button"
            className={`ooa-main-topbar__ai-btn${
              visualizeOpen ? " ooa-main-topbar__ai-btn--active" : ""
            } ooa-main-topbar__ai-btn--visualize`}
            aria-label="Visualize"
            title="Visualize — PDF & Excel reports"
            aria-pressed={visualizeOpen}
            onClick={onToggleVisualize}
          >
            <IconVisualize size={18} />
            <span className="ooa-main-topbar__btn-label">Visualize</span>
          </button>
        ) : null}
        {onBuildDashboard ? (
          <button
            type="button"
            className="ooa-main-topbar__ai-btn ooa-main-topbar__ai-btn--dashboard"
            aria-label="Build My Dashboard"
            title="Build My Dashboard (coming soon)"
            onClick={onBuildDashboard}
          >
            <IconDashboard size={18} />
            <span className="ooa-main-topbar__btn-label">Dashboard</span>
          </button>
        ) : null}
        {onNewChat ? (
          <button
            type="button"
            className="ooa-main-topbar__icon-btn ooa-main-topbar__text-btn"
            aria-label="New chat"
            title="New chat"
            onClick={onNewChat}
          >
            <IconNewChat />
            <span className="ooa-main-topbar__btn-label">New chat</span>
          </button>
        ) : null}
        {onOpenChats ? (
          <button
            type="button"
            className="ooa-main-topbar__icon-btn ooa-main-topbar__text-btn"
            aria-label="Past chats"
            title="Past chats"
            onClick={onOpenChats}
          >
            <IconChats />
            <span className="ooa-main-topbar__btn-label">Chats</span>
          </button>
        ) : null}
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
