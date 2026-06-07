import { formatDateRangeBadge } from "../../utils/chat";

export default function DateRangeBadge({ dateFrom, dateTo, defaulted }) {
  const label = formatDateRangeBadge(dateFrom, dateTo, { defaulted });
  if (!label) return null;

  return (
    <div className="ooa-date-badge" title="Report period">
      <span aria-hidden="true">📅</span>
      <span>{label}</span>
    </div>
  );
}
