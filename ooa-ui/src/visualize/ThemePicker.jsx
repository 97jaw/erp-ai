export default function ThemePicker({ themes, value, onChange, disabled, embedded = false }) {
  if (!themes?.length) return null;

  return (
    <div className={`ooa-viz-picker${embedded ? " ooa-viz-picker--embedded" : ""}`} role="group" aria-label="PDF theme">
      {!embedded ? <span className="ooa-viz-picker__label">Theme</span> : null}
      <div className="ooa-viz-picker__options">
        {themes.map((theme) => {
          const active = value === theme.id;
          const preview = theme.preview || {};
          return (
            <button
              key={theme.id}
              type="button"
              className={`ooa-viz-picker__chip${active ? " ooa-viz-picker__chip--active" : ""}`}
              disabled={disabled}
              onClick={() => onChange(theme.id)}
              title={theme.description}
            >
              <span
                className="ooa-viz-picker__swatch"
                style={{
                  background: `linear-gradient(135deg, ${preview.primary || "#1a2744"} 0%, ${preview.secondary || "#c9a84c"} 50%, ${preview.background || "#fff"} 100%)`,
                }}
              />
              <span className="ooa-viz-picker__name">{theme.name}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
