import { useState } from "react";
import { IconDiamond, QuickActionIcon } from "../../components/common/MainIcons";
import { formatQueryAge } from "../../utils/layoutContent";
import { QUICK_ACTION_ITEMS } from "./quickActions";
import PastChatsPanel from "./PastChatsPanel";

export default function QuickActionsSidebar({
  queries = [],
  activeQueryId,
  onQuickAction,
  onSelectHistory,
  onExpandedChange,
  pastChats = [],
  pastChatsLoading = false,
  pastChatsError = null,
  activeConversationId = null,
  onLoadPastChat,
  onRefreshPastChats,
  onNewChat,
  onDeleteChat,
}) {
  const [expanded, setExpanded] = useState(false);

  const toggleExpanded = () => {
    setExpanded((value) => {
      const next = !value;
      onExpandedChange?.(next);
      return next;
    });
  };

  return (
    <aside
      className={`ooa-quick-sidebar${expanded ? " ooa-quick-sidebar--expanded" : ""}`}
      aria-label="Quick actions"
    >
      <button
        type="button"
        className="ooa-quick-sidebar__logo"
        onClick={toggleExpanded}
        aria-expanded={expanded}
        title={expanded ? "Collapse sidebar" : "Expand sidebar — Past chats"}
      >
        <IconDiamond size={18} />
        {expanded ? <span className="ooa-quick-sidebar__logo-text">OOA</span> : null}
      </button>

      <nav className="ooa-quick-sidebar__nav">
        {QUICK_ACTION_ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            className="ooa-quick-sidebar__item"
            title={item.label}
            onClick={() => onQuickAction?.(item)}
          >
            <span className="ooa-quick-sidebar__icon" aria-hidden="true">
              <QuickActionIcon name={item.icon} size={20} />
            </span>
            {expanded ? <span className="ooa-quick-sidebar__label">{item.label}</span> : null}
          </button>
        ))}
      </nav>

      {expanded ? (
        <PastChatsPanel
          conversations={pastChats}
          loading={pastChatsLoading}
          error={pastChatsError}
          activeConversationId={activeConversationId}
          onSelect={onLoadPastChat}
          onRefresh={onRefreshPastChats}
          onNewChat={onNewChat}
          onDelete={onDeleteChat}
        />
      ) : null}

      {expanded && queries.length ? (
        <section className="ooa-quick-sidebar__section" aria-label="This session">
          <h3 className="ooa-quick-sidebar__section-title">This session</h3>
          <ul className="ooa-quick-sidebar__history">
            {queries.slice(0, 6).map((query) => (
              <li key={query.id}>
                <button
                  type="button"
                  className={`ooa-quick-sidebar__history-item${
                    query.id === activeQueryId ? " ooa-quick-sidebar__history-item--active" : ""
                  }`}
                  onClick={() => onSelectHistory?.(query.id)}
                >
                  <span className="ooa-quick-sidebar__history-q">
                    {query.question.slice(0, 48)}
                    {query.question.length > 48 ? "…" : ""}
                  </span>
                  <span className="ooa-quick-sidebar__history-age">
                    {formatQueryAge(query.createdAt)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </aside>
  );
}
