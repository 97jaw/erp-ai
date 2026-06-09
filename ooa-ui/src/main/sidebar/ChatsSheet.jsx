import { useEffect, useRef } from "react";
import PastChatsPanel from "./PastChatsPanel";

export default function ChatsSheet({
  open = false,
  onClose,
  conversations = [],
  loading = false,
  error = null,
  activeConversationId = null,
  onSelect,
  onRefresh,
  onNewChat,
  onDelete,
}) {
  const panelRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;

    const onKeyDown = (event) => {
      if (event.key === "Escape") onClose?.();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    if (open) {
      panelRef.current?.focus();
    }
  }, [open]);

  if (!open) return null;

  return (
    <div className="ooa-chats-sheet" role="presentation">
      <button
        type="button"
        className="ooa-chats-sheet__backdrop"
        aria-label="Close chats panel"
        onClick={onClose}
      />
      <aside
        ref={panelRef}
        className="ooa-chats-sheet__panel"
        role="dialog"
        aria-modal="true"
        aria-label="Past chats"
        tabIndex={-1}
      >
        <header className="ooa-chats-sheet__header">
          <h2 className="ooa-chats-sheet__title">Chats</h2>
          <button
            type="button"
            className="ooa-chats-sheet__close"
            onClick={onClose}
            aria-label="Close"
          >
            ×
          </button>
        </header>
        <PastChatsPanel
          conversations={conversations}
          loading={loading}
          error={error}
          activeConversationId={activeConversationId}
          onSelect={(conversation) => {
            onSelect?.(conversation);
            onClose?.();
          }}
          onRefresh={onRefresh}
          onNewChat={() => {
            onNewChat?.();
            onClose?.();
          }}
          onDelete={onDelete}
        />
      </aside>
    </div>
  );
}
