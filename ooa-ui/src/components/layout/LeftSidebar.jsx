import { SHOWCASE_FEATURES } from "../../utils/layoutContent";

export default function LeftSidebar({ onSelectQuery, compact = false }) {
  return (
    <aside className={`ooa-left-sidebar ${compact ? "ooa-left-sidebar--compact" : ""}`} aria-label="Quick links">
      {SHOWCASE_FEATURES.map((feature) => (
        <button
          key={feature.id}
          type="button"
          className="ooa-quick-link"
          title={feature.title}
          onClick={() => onSelectQuery(feature.query)}
        >
          <span className="ooa-quick-link__icon" aria-hidden="true">{feature.icon}</span>
          <span className="ooa-quick-link__label">{feature.title}</span>
        </button>
      ))}
    </aside>
  );
}
