import { motion } from "framer-motion";
import { QUICK_ACTIONS } from "../../utils/chat";

export default function Sidebar({ history, loading, onQuickAction, onHistorySelect }) {
  return (
    <aside className="ooa-sidebar">
      <div className="ooa-sidebar__section-title">Quick Actions</div>
      {QUICK_ACTIONS.map((action) => (
        <motion.button
          key={action.label}
          type="button"
          className="ooa-quick-action"
          whileHover={{ y: -2 }}
          whileTap={{ scale: 0.98 }}
          disabled={loading}
          onClick={() => onQuickAction(action.query)}
        >
          <span className="ooa-quick-action__icon">{action.icon}</span>
          <span className="ooa-quick-action__label">{action.label}</span>
        </motion.button>
      ))}

      <div className="ooa-sidebar__section-title ooa-sidebar__section-title--spaced">History</div>
      {history.length ? (
        <div className="ooa-sidebar__history">
          {history.map((item) => (
            <button
              key={item}
              type="button"
              className="ooa-sidebar__history-item"
              onClick={() => onHistorySelect(item)}
            >
              {item}
            </button>
          ))}
        </div>
      ) : (
        <div className="ooa-sidebar__empty">Your recent questions will appear here.</div>
      )}
    </aside>
  );
}
