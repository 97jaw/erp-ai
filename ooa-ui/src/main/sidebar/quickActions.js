/** Primary sidebar navigation — chat lane only (no quick-action queries). */
export const SIDEBAR_NAV_ITEMS = [
  { id: "search", icon: "search", label: "Search", action: "focus" },
  { id: "chat-list", icon: "chats", label: "Chat List", action: "chat-list" },
  { id: "sessions", icon: "clock", label: "Sessions", action: "sessions" },
];

/** Audit lane — pinned at bottom of the sidebar. */
export const AUDIT_NAV_ITEM = {
  id: "audit",
  icon: "audit",
  label: "Audit",
  action: "audit",
};
