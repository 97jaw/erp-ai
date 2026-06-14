import { useEffect, useRef, useState } from "react";
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
import useViewportTier from "../../hooks/useViewportTier";

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
  onCloseAudit,
  onOpenReports,
  onToggleVisualize,
  onBuildDashboard,
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const viewportTier = useViewportTier();
  const [tooltip, setTooltip] = useState(null);
  const [integrationsOpen, setIntegrationsOpen] = useState(false);
  const [utilityMenuOpen, setUtilityMenuOpen] = useState(false);
  const integrationsRef = useRef(null);
  const utilityMenuRef = useRef(null);
  const onIntegration = location.pathname.startsWith("/integrations");
  const compactIntegrations = viewportTier !== "desktop";
  const isMobile = viewportTier === "mobile";
  const isAuditView = mainView === "audit";
  const isReportsView = mainView === "reports";

  useEffect(() => {
    if (!integrationsOpen) return undefined;
    const onPointerDown = (event) => {
      if (integrationsRef.current?.contains(event.target)) return;
      setIntegrationsOpen(false);
    };
    const onKeyDown = (event) => {
      if (event.key === "Escape") setIntegrationsOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [integrationsOpen]);

  useEffect(() => {
    if (!utilityMenuOpen) return undefined;
    const onPointerDown = (event) => {
      if (utilityMenuRef.current?.contains(event.target)) return;
      setUtilityMenuOpen(false);
    };
    const onKeyDown = (event) => {
      if (event.key === "Escape") setUtilityMenuOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [utilityMenuOpen]);

  const handleAuditClick = () => {
    if (isAuditView) {
      onCloseAudit?.();
      return;
    }
    onOpenAudit?.();
  };

  const renderIntegrationButton = (integration, className = "ooa-main-topbar__integration") => {
    const active = location.pathname === integration.path;
    return (
      <button
        key={integration.id}
        type="button"
        className={`${className}${active ? ` ${className}--active` : ""}`}
        aria-label={`${integration.name} integration`}
        aria-current={active ? "page" : undefined}
        onMouseEnter={() => showTooltip(integration)}
        onMouseLeave={() => setTooltip(null)}
        onFocus={() => showTooltip(integration)}
        onBlur={() => setTooltip(null)}
        onClick={() => {
          setIntegrationsOpen(false);
          navigate(integration.path);
        }}
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
  };

  const showTooltip = (integration) => {
    const statusLabel =
      integration.status === "connected"
        ? "Connected"
        : integration.status === "error"
          ? "Disconnected"
          : "Not connected";
    setTooltip({ name: integration.name, status: statusLabel });
  };

  const integrationsMenu = (
    <div className="ooa-main-topbar__integrations-menu" ref={integrationsRef}>
      <button
        type="button"
        className={`ooa-main-topbar__icon-btn ooa-main-topbar__integrations-trigger${
          integrationsOpen ? " ooa-main-topbar__integrations-trigger--open" : ""
        }${onIntegration ? " ooa-main-topbar__integrations-trigger--active" : ""}`}
        aria-label="Integrations"
        aria-expanded={integrationsOpen}
        aria-haspopup="menu"
        title="Integrations"
        onClick={() => setIntegrationsOpen((value) => !value)}
      >
        <span aria-hidden="true">⋯</span>
      </button>
      {integrationsOpen ? (
        <div className="ooa-main-topbar__integrations-dropdown" role="menu">
          {INTEGRATIONS.map((integration) => {
            const active = location.pathname === integration.path;
            const statusLabel =
              integration.status === "connected"
                ? "Connected"
                : integration.status === "error"
                  ? "Disconnected"
                  : "Not connected";
            return (
              <button
                key={integration.id}
                type="button"
                role="menuitem"
                className={`ooa-main-topbar__integrations-item${
                  active ? " ooa-main-topbar__integrations-item--active" : ""
                }`}
                onClick={() => {
                  setIntegrationsOpen(false);
                  navigate(integration.path);
                }}
              >
                <span className="ooa-main-topbar__integrations-item-icon" aria-hidden="true">
                  <IconIntegration id={integration.id} />
                </span>
                <span className="ooa-main-topbar__integrations-item-text">
                  <span className="ooa-main-topbar__integrations-item-name">
                    {integration.name}
                  </span>
                  <span className="ooa-main-topbar__integrations-item-status">
                    {statusLabel}
                  </span>
                </span>
                <span
                  className={`ooa-main-topbar__dot ${statusDotClass(integration.status)}`}
                  aria-hidden="true"
                />
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );

  return (
    <header
      className={`ooa-main-topbar${isAuditView ? " ooa-main-topbar--audit-view" : ""}${
        isMobile ? " ooa-main-topbar--mobile" : ""
      }`}
      role="banner"
    >
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
        {!compactIntegrations
          ? INTEGRATIONS.map((integration) => renderIntegrationButton(integration))
          : null}
        {tooltip && !compactIntegrations ? (
          <span className="ooa-main-topbar__tooltip" role="tooltip">
            {tooltip.name} · {tooltip.status}
          </span>
        ) : null}
      </div>

      <div className="ooa-main-topbar__group ooa-main-topbar__group--utility">
        {compactIntegrations ? integrationsMenu : null}
        {onOpenAudit ? (
          <button
            type="button"
            className={`ooa-main-topbar__ai-btn${
              isAuditView ? " ooa-main-topbar__ai-btn--active" : ""
            } ooa-main-topbar__ai-btn--audit`}
            aria-label={isAuditView ? "Close audit — back to chat" : "Audit"}
            title={isAuditView ? "Back to chat" : "Audit — change history & activity"}
            aria-pressed={isAuditView}
            onClick={handleAuditClick}
          >
            <IconAudit size={18} />
            <span className="ooa-main-topbar__btn-label">Audit</span>
          </button>
        ) : null}
        {onOpenReports ? (
          <button
            type="button"
            className={`ooa-main-topbar__ai-btn ooa-main-topbar__ai-btn--reports${
              isReportsView ? " ooa-main-topbar__ai-btn--active" : ""
            }`}
            aria-label={isReportsView ? "Close reports — back to chat" : "Reports"}
            title={isReportsView ? "Back to chat" : "Reports — generate financial reports"}
            aria-pressed={isReportsView}
            onClick={onOpenReports}
          >
            <span aria-hidden="true" style={{ fontSize: 16, lineHeight: 1 }}>📊</span>
            <span className="ooa-main-topbar__btn-label">Reports</span>
          </button>
        ) : null}
        {!isAuditView && onToggleVisualize ? (
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
        {!isAuditView && !isMobile && onBuildDashboard ? (
          <button
            type="button"
            className="ooa-main-topbar__ai-btn ooa-main-topbar__ai-btn--dashboard"
            aria-label="Build Dashboard"
            title="Build Dashboard (coming soon)"
            onClick={onBuildDashboard}
          >
            <IconDashboard size={18} />
            <span className="ooa-main-topbar__btn-label">Build Dashboard</span>
          </button>
        ) : null}
        {!isAuditView && !isMobile && onNewChat ? (
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
        {!isMobile ? (
          <>
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
          </>
        ) : (
          <div className="ooa-main-topbar__utility-menu" ref={utilityMenuRef}>
            <button
              type="button"
              className={`ooa-main-topbar__icon-btn ooa-main-topbar__utility-menu-trigger${
                utilityMenuOpen ? " ooa-main-topbar__utility-menu-trigger--open" : ""
              }`}
              aria-label="More actions"
              aria-expanded={utilityMenuOpen}
              aria-haspopup="menu"
              title="More"
              onClick={() => setUtilityMenuOpen((value) => !value)}
            >
              <span aria-hidden="true">⋮</span>
            </button>
            {utilityMenuOpen ? (
              <div className="ooa-main-topbar__utility-dropdown" role="menu">
                {!isAuditView && onBuildDashboard ? (
                  <button
                    type="button"
                    role="menuitem"
                    className="ooa-main-topbar__utility-dropdown-item"
                    onClick={() => {
                      setUtilityMenuOpen(false);
                      onBuildDashboard();
                    }}
                  >
                    Build Dashboard
                  </button>
                ) : null}
                {!isAuditView && onNewChat ? (
                  <button
                    type="button"
                    role="menuitem"
                    className="ooa-main-topbar__utility-dropdown-item"
                    onClick={() => {
                      setUtilityMenuOpen(false);
                      onNewChat();
                    }}
                  >
                    New chat
                  </button>
                ) : null}
                <button
                  type="button"
                  role="menuitem"
                  className="ooa-main-topbar__utility-dropdown-item"
                  onClick={() => {
                    setUtilityMenuOpen(false);
                    onOpenSearch?.();
                  }}
                >
                  Search
                </button>
                <button
                  type="button"
                  role="menuitem"
                  className="ooa-main-topbar__utility-dropdown-item"
                  onClick={() => setUtilityMenuOpen(false)}
                >
                  Notifications
                </button>
                {isAuditView && onCloseAudit ? (
                  <button
                    type="button"
                    role="menuitem"
                    className="ooa-main-topbar__utility-dropdown-item"
                    onClick={() => {
                      setUtilityMenuOpen(false);
                      onCloseAudit();
                    }}
                  >
                    Back to chat
                  </button>
                ) : null}
                <div className="ooa-main-topbar__utility-dropdown-theme" role="none">
                  <MainThemeMenu />
                </div>
              </div>
            ) : null}
          </div>
        )}
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
