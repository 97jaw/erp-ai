const FORMATS = [
  { id: "pdf", label: "PDF", icon: "📄" },
  { id: "excel", label: "Excel", icon: "📊" },
];

export default function FormatPicker({ value, recommended, onChange, disabled }) {
  const recommendedFmt = (recommended || "pdf").toLowerCase();

  return (
    <div className="ooa-viz-format" role="radiogroup" aria-label="Output format">
      {FORMATS.map((fmt) => {
        const active = value === fmt.id;
        const isRecommended =
          fmt.id === recommendedFmt
          || (fmt.id === "excel" && recommendedFmt === "xlsx");
        return (
          <button
            key={fmt.id}
            type="button"
            role="radio"
            aria-checked={active}
            className={`ooa-viz-format__chip${active ? " ooa-viz-format__chip--active" : ""}`}
            disabled={disabled}
            onClick={() => onChange(fmt.id)}
          >
            <span className="ooa-viz-format__icon" aria-hidden="true">{fmt.icon}</span>
            <span className="ooa-viz-format__label">{fmt.label}</span>
            {isRecommended ? (
              <span className="ooa-viz-format__rec">Recommended</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
