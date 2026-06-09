export default function OverBudgetBadge({ show, label = "Over budget" }) {
  if (!show) return null;
  return <span className="ooa-pe-badge ooa-pe-badge--critical">{label}</span>;
}
