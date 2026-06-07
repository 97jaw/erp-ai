export default function LayoutPicker({ layouts, value, onChange, disabled, embedded = false }) {
  if (!layouts?.length) return null;

  return (
    <div className={`ooa-viz-picker${embedded ? " ooa-viz-picker--embedded" : ""}`} role="group" aria-label="PDF layout">
      {!embedded ? <span className="ooa-viz-picker__label">Layout</span> : null}
      <div className="ooa-viz-picker__options ooa-viz-picker__options--stack">
        {layouts.map((layout) => {
          const active = value === layout.id;
          return (
            <button
              key={layout.id}
              type="button"
              className={`ooa-viz-picker__chip ooa-viz-picker__chip--wide${active ? " ooa-viz-picker__chip--active" : ""}`}
              disabled={disabled}
              onClick={() => onChange(layout.id)}
              title={layout.description}
            >
              <span className="ooa-viz-picker__name">{layout.name}</span>
              <span className="ooa-viz-picker__desc">{layout.description}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
