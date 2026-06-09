import { formatConversationWhen } from "../../utils/chatHistory";

export default function PastChatsPanel({
  conversations = [],
  loading = false,
  error = null,
  activeConversationId = null,
  onSelect,
  onRefresh,
  onNewChat,
  onDelete,
}) {
  return (
    <section className="ooa-past-chats" aria-label="Past chats">
      <div className="ooa-past-chats__header">
        <h3 className="ooa-past-chats__title">Past chats</h3>
        <div className="ooa-past-chats__actions">
          <button
            type="button"
            className="ooa-past-chats__action"
            onClick={onNewChat}
            title="Start new chat"
          >
            New
          </button>
          <button
            type="button"
            className="ooa-past-chats__action"
            onClick={onRefresh}
            disabled={loading}
            title="Refresh list"
          >
            {loading ? "…" : "↻"}
          </button>
        </div>
      </div>

      {error ? (
        <p className="ooa-past-chats__error" role="alert">{error}</p>
      ) : null}

      {!loading && !conversations.length && !error ? (
        <p className="ooa-past-chats__empty">
          No saved chats yet. Ask a question and it will appear here after you log in.
        </p>
      ) : null}

      <div className="ooa-past-chats__scroll">
        <ul className="ooa-past-chats__list">
          {conversations.map((conv) => {
          const title = (conv.title || "Untitled chat").trim();
          const when = formatConversationWhen(conv.last_message_at || conv.started_at);
          const isActive = conv.id === activeConversationId;

          return (
            <li key={conv.id} className="ooa-past-chats__row">
              <button
                type="button"
                className={`ooa-past-chats__item${isActive ? " ooa-past-chats__item--active" : ""}`}
                onClick={() => onSelect?.(conv)}
                title={title}
              >
                <span className="ooa-past-chats__item-title">
                  {title.length > 52 ? `${title.slice(0, 49)}…` : title}
                </span>
                <span className="ooa-past-chats__item-meta">
                  <span>{when}</span>
                  {conv.message_count ? (
                    <>
                      <span aria-hidden="true">·</span>
                      <span>{conv.message_count} msgs</span>
                    </>
                  ) : null}
                </span>
              </button>
              {onDelete ? (
                <button
                  type="button"
                  className="ooa-past-chats__delete"
                  onClick={(event) => {
                    event.stopPropagation();
                    onDelete?.(conv);
                  }}
                  disabled={loading}
                  aria-label={`Delete chat: ${title}`}
                  title="Delete chat"
                >
                  ×
                </button>
              ) : null}
            </li>
          );
        })}
        </ul>
      </div>
    </section>
  );
}
