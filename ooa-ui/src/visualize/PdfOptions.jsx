const WATERMARKS = [
  { id: "none", label: "No watermark" },
  { id: "confidential", label: "Confidential" },
  { id: "draft", label: "Draft" },
];

export default function PdfOptions({
  includeLogo,
  pageNumbers,
  watermark,
  onIncludeLogoChange,
  onPageNumbersChange,
  onWatermarkChange,
  disabled,
  embedded = false,
}) {
  return (
    <div
      className={`ooa-viz-pdf-options${embedded ? " ooa-viz-pdf-options--embedded" : ""}`}
      role="group"
      aria-label="PDF options"
    >
      {!embedded ? <span className="ooa-viz-picker__label">PDF options</span> : null}
      <div className="ooa-viz-pdf-options__toggles">
        <label className="ooa-viz-pdf-options__toggle">
          <input
            type="checkbox"
            checked={includeLogo}
            disabled={disabled}
            onChange={(event) => onIncludeLogoChange(event.target.checked)}
          />
          Company logo
        </label>
        <label className="ooa-viz-pdf-options__toggle">
          <input
            type="checkbox"
            checked={pageNumbers}
            disabled={disabled}
            onChange={(event) => onPageNumbersChange(event.target.checked)}
          />
          Page numbers
        </label>
      </div>
      <label className="ooa-viz-pdf-options__select-wrap">
        <span className="ooa-viz-pdf-options__select-label">Watermark</span>
        <select
          className="ooa-viz-pdf-options__select"
          value={watermark}
          disabled={disabled}
          onChange={(event) => onWatermarkChange(event.target.value)}
        >
          {WATERMARKS.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
