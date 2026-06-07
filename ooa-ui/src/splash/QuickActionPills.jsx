import { useState } from "react";
import { QUICK_ACTIONS } from "./quickActions";

export default function QuickActionPills({ isLoggedIn, className = "", onPillClick, onVoiceClick }) {
  const [activeId, setActiveId] = useState(null);

  return (
    <div className={`splash-pills${className ? ` ${className}` : ""}`} role="group" aria-label="Quick actions">
      {QUICK_ACTIONS.map((pill) => (
        <button
          key={pill.id}
          type="button"
          className={`splash-pill${activeId === pill.id ? " splash-pill--active" : ""}`}
          onClick={() => {
            setActiveId(pill.id);
            if (pill.action === "voice") {
              onVoiceClick?.();
            } else {
              onPillClick?.(pill.query, pill);
            }
          }}
          title={!isLoggedIn ? "Sign in to use this action" : undefined}
        >
          <span aria-hidden="true">{pill.icon} </span>
          {pill.label}
        </button>
      ))}
    </div>
  );
}
