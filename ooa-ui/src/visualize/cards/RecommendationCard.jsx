export default function RecommendationCard({ recommendation, onAction, disabled = false, embedded = false }) {
  if (!recommendation) return null;

  const sections = recommendation.section_labels || recommendation.sections?.map((s) => s.label || s.type) || [];

  return (
    <div className="viz-analysis-card recommendation-card">
      <div className="viz-analysis-card__title">My recommendation</div>

      <div className="rec-grid">
        <div className="rec-row">
          <span className="rec-label">Format</span>
          <span className="rec-value">{recommendation.format_display || recommendation.format}</span>
        </div>
        <div className="rec-row">
          <span className="rec-label">Layout</span>
          <span className="rec-value">{recommendation.layout_display || recommendation.layout}</span>
        </div>
        <div className="rec-row">
          <span className="rec-label">Theme</span>
          <span className="rec-value">{recommendation.theme_display || recommendation.theme}</span>
        </div>
        <div className="rec-row">
          <span className="rec-label">Est. pages</span>
          <span className="rec-value">{recommendation.estimated_pages}</span>
        </div>
      </div>

      {sections.length ? (
        <div className="sections-list">
          <div className="sections-list__title">This report will include:</div>
          {sections.map((section) => (
            <div key={section} className="section-item">
              <span className="section-item__check">✓</span>
              <span>{section}</span>
            </div>
          ))}
        </div>
      ) : null}

      {recommendation.reasoning ? (
        <div className="reasoning">
          <div className="reasoning__title">Why this approach</div>
          <p>{recommendation.reasoning}</p>
        </div>
      ) : null}

      <div className="recommendation-card__actions">
        {!embedded ? (
          <button
            type="button"
            className="viz-btn viz-btn--primary"
            disabled={disabled}
            onClick={() => onAction?.("build", recommendation)}
          >
            Build this report →
          </button>
        ) : null}
        <button
          type="button"
          className="viz-btn viz-btn--secondary"
          disabled={disabled}
          onClick={() => onAction?.("customize", recommendation)}
        >
          Customize first
        </button>
        <button
          type="button"
          className="viz-btn viz-btn--tertiary"
          disabled={disabled}
          onClick={() => onAction?.("alternatives", recommendation)}
        >
          Different
        </button>
      </div>
    </div>
  );
}
