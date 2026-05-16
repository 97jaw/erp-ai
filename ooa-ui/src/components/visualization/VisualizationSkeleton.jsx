const SKELETON_TYPES = {
  KPI_CARD: "kpi",
  BAR_CHART: "chart",
  LINE_CHART: "chart",
  DATA_TABLE: "table",
  FINANCIAL_REPORT: "financial",
  PDF_REPORT: "pdf",
};

export default function VisualizationSkeleton({ type = "kpi" }) {
  const resolved = SKELETON_TYPES[type] || "kpi";

  if (resolved === "chart") {
    return (
      <div className="ooa-skeleton ooa-skeleton--chart" aria-hidden="true">
        <div className="ooa-skeleton__label shimmer" />
        <div className="ooa-skeleton__bars">
          {[0, 1, 2, 3].map((index) => (
            <div key={index} className="ooa-skeleton__bar shimmer" style={{ height: `${40 + index * 12}%` }} />
          ))}
        </div>
        <div className="ooa-skeleton__caption">Generating chart...</div>
      </div>
    );
  }

  if (resolved === "table") {
    return (
      <div className="ooa-skeleton ooa-skeleton--table" aria-hidden="true">
        <div className="ooa-skeleton__label shimmer" />
        <div className="ooa-skeleton__row shimmer" />
        <div className="ooa-skeleton__row shimmer" />
        <div className="ooa-skeleton__row shimmer" />
        <div className="ooa-skeleton__row shimmer" />
      </div>
    );
  }

  if (resolved === "financial") {
    return (
      <div className="ooa-skeleton ooa-skeleton--financial" aria-hidden="true">
        <div className="ooa-skeleton__label shimmer" />
        <div className="ooa-skeleton__grid">
          {[0, 1, 2, 3].map((index) => (
            <div key={index} className="ooa-skeleton__metric shimmer" />
          ))}
        </div>
      </div>
    );
  }

  if (resolved === "pdf") {
    return (
      <div className="ooa-skeleton ooa-skeleton--pdf" aria-hidden="true">
        <div className="ooa-skeleton__page shimmer" />
        <div className="ooa-skeleton__caption">Generating PDF...</div>
      </div>
    );
  }

  return (
    <div className="ooa-skeleton ooa-skeleton--kpi" aria-hidden="true">
      <div className="ooa-skeleton__label shimmer" />
      <div className="ooa-skeleton__value shimmer" />
      <div className="ooa-skeleton__row shimmer" />
      <div className="ooa-skeleton__row shimmer" />
    </div>
  );
}
