import { useState } from "react";
import { formatAuditTime } from "./auditUtils";

function ModelGroup({ group, onRecordSelect }) {
  const [open, setOpen] = useState(true);
  const records = group.records || [];

  return (
    <div className={`ooa-audit-activity-group${open ? " ooa-audit-activity-group--open" : ""}`}>
      <button
        type="button"
        className="ooa-audit-activity-group__head"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <span className="ooa-audit-activity-group__label">
          {group.model_label || group.model}
        </span>
        <span className="ooa-audit-activity-group__badge">
          {group.records_changed ?? records.length}
        </span>
        <span className="ooa-audit-activity-group__chevron" aria-hidden="true">
          {open ? "▾" : "▸"}
        </span>
      </button>

      {open ? (
        <ul className="ooa-audit-activity-group__list">
          {records.map((record) => (
            <li key={`${group.model}-${record.id}`}>
              <button
                type="button"
                className="ooa-audit-activity-record"
                onClick={() =>
                  onRecordSelect?.({
                    model: group.model,
                    recordId: record.id,
                    name: record.name,
                  })
                }
              >
                <span className="ooa-audit-activity-record__name">{record.name}</span>
                <span className="ooa-audit-activity-record__meta">
                  {record.changes} {record.changes === 1 ? "change" : "changes"}
                  {record.last_change ? ` · ${formatAuditTime(record.last_change)}` : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export default function AuditActivityLog({ byModel = [], onRecordSelect, emptyMessage }) {
  if (!byModel.length) {
    return (
      <div className="ooa-audit-empty">
        {emptyMessage || "No user activity recorded for this period."}
      </div>
    );
  }

  return (
    <section className="ooa-audit-activity" aria-label="Activity by model">
      {byModel.map((group) => (
        <ModelGroup
          key={group.model}
          group={group}
          onRecordSelect={onRecordSelect}
        />
      ))}
    </section>
  );
}
