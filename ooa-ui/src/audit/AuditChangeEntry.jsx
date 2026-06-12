import { useState } from "react";
import { formatAuditTime, initialsFromName } from "./auditUtils";

export default function AuditChangeEntry({ entry, defaultExpanded = false }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const fieldChanges = entry?.field_changes || [];
  const hasBody = Boolean(entry?.body_text?.trim());
  const hasDetails =
    fieldChanges.length > 0 || hasBody || entry?.message_type || entry?.subtype;

  return (
    <article className={`ooa-audit-entry${expanded ? " ooa-audit-entry--open" : ""}`}>
      <div className="ooa-audit-entry__rail">
        <span className="ooa-audit-entry__dot" aria-hidden="true" />
      </div>

      <div className="ooa-audit-entry__body">
        <header className="ooa-audit-entry__header">
          <time className="ooa-audit-entry__time">{formatAuditTime(entry?.date)}</time>
          <div className="ooa-audit-entry__who">
            <span className="ooa-audit-entry__avatar" aria-hidden="true">
              {initialsFromName(entry?.author)}
            </span>
            <span className="ooa-audit-entry__author">{entry?.author || "Unknown"}</span>
          </div>
          {hasDetails ? (
            <button
              type="button"
              className="ooa-audit-entry__toggle"
              onClick={() => setExpanded((value) => !value)}
              aria-expanded={expanded}
            >
              {expanded ? "Less" : "Details"}
            </button>
          ) : null}
        </header>

        {fieldChanges.length > 0 ? (
          <div className="ooa-audit-entry__pills">
            {fieldChanges.map((change, index) => (
              <span
                key={`${change.field}-${index}`}
                className="ooa-audit-entry__pill"
                title={`${change.old} → ${change.new}`}
              >
                <strong>{change.field}:</strong> {change.old || "—"} → {change.new || "—"}
              </span>
            ))}
          </div>
        ) : null}

        {hasBody && (!hasDetails || expanded) ? (
          <p className="ooa-audit-entry__comment">{entry.body_text}</p>
        ) : null}

        {expanded && (entry?.message_type || entry?.subtype) ? (
          <footer className="ooa-audit-entry__meta">
            {[entry.message_type, entry.subtype].filter(Boolean).join(" · ")}
          </footer>
        ) : null}
      </div>
    </article>
  );
}
