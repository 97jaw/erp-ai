import { formatQueryAge } from "../../utils/layoutContent";

const VIZ_ICONS = {
  KPI_CARD: "📊",
  BAR_CHART: "📊",
  FINANCIAL_REPORT: "📊",
  DATA_TABLE: "📋",
  PDF_REPORT: "📄",
};

export default function QueryTab({
  query,
  tabNumber,
  active,
  onSelect,
  onClose,
  onReask,
}) {
  const vizIcon = VIZ_ICONS[query.vizType] || (query.vizType ? "📊" : null);

  return (
    <div className={`ooa-query-tab ${active ? "ooa-query-tab--active" : ""}`}>
      <button type="button" className="ooa-query-tab__body" onClick={() => onSelect(query.id)}>
        <span className="ooa-query-tab__header">
          <span className="ooa-query-tab__label">Query {tabNumber}</span>
          {active ? <span className="ooa-query-tab__active">active</span> : null}
        </span>
        <span className="ooa-query-tab__question">{query.question}</span>
        <span className="ooa-query-tab__meta">{formatQueryAge(query.createdAt)}</span>
        <span className="ooa-query-tab__footer">
          {query.vizType ? (
            <span className="ooa-query-tab__badge">{vizIcon} {query.vizType}</span>
          ) : null}
          <span className="ooa-query-tab__chat" aria-hidden="true">💬</span>
        </span>
      </button>
      <div className="ooa-query-tab__actions">
        <button type="button" title="Re-ask" onClick={() => onReask(query.question)}>↺</button>
        <button type="button" title="Close" onClick={() => onClose(query.id)}>×</button>
      </div>
    </div>
  );
}
