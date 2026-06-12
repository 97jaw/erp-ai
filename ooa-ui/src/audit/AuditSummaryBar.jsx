import { buildSummaryFromAuditData } from "./auditUtils";

export default function AuditSummaryBar({ auditData, period }) {
  const summary = buildSummaryFromAuditData(auditData);
  if (!summary) return null;

  const periodLabel =
    period?.from || period?.to
      ? [period.from, period.to].filter(Boolean).join(" → ")
      : null;

  const usersLabel =
    summary.userCount === 0
      ? "no users"
      : summary.userCount === 1
        ? summary.authors[0] || "1 user"
        : `${summary.userCount} users`;

  return (
    <div className="ooa-audit-summary" role="status">
      <div className="ooa-audit-summary__metric">
        <span className="ooa-audit-summary__value">{summary.changeCount}</span>
        <span className="ooa-audit-summary__label">
          {summary.changeCount === 1 ? "change" : "changes"}
        </span>
      </div>
      <div className="ooa-audit-summary__divider" aria-hidden="true" />
      <div className="ooa-audit-summary__detail">
        <span className="ooa-audit-summary__users">{usersLabel}</span>
        {periodLabel ? (
          <span className="ooa-audit-summary__period">{periodLabel}</span>
        ) : null}
        {summary.label ? (
          <span className="ooa-audit-summary__subject">{summary.label}</span>
        ) : null}
      </div>
    </div>
  );
}
