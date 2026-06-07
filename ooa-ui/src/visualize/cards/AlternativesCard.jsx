export default function AlternativesCard({ alternatives = [], onSelect, onBack, disabled = false, embedded = false }) {
  if (!alternatives.length) return null;

  const icons = { excel: "📊", ppt: "📈", pdf: "📋" };
  const cardClass = embedded
    ? "viz-analysis-card viz-analysis-card--embedded alternatives-card"
    : "viz-analysis-card alternatives-card";

  return (
    <div className={cardClass}>
      {!embedded ? <div className="viz-analysis-card__title">Other options</div> : null}
      <div className="alternatives-card__list">
        {alternatives.map((alt) => (
          <div key={alt.label} className="alternative-option">
            <div className="alternative-option__icon">{icons[alt.format] || "📄"}</div>
            <div className="alternative-option__body">
              <div className="alternative-option__label">{alt.label}</div>
              <p className="alternative-option__desc">{alt.description}</p>
            </div>
            <button
              type="button"
              className="viz-btn viz-btn--secondary"
              disabled={disabled}
              onClick={() => onSelect?.(alt)}
            >
              Choose this
            </button>
          </div>
        ))}
      </div>
      {onBack ? (
        <button type="button" className="viz-btn viz-btn--tertiary" onClick={onBack}>
          ← Back to recommendation
        </button>
      ) : null}
    </div>
  );
}
