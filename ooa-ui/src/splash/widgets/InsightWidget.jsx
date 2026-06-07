export default function InsightWidget({ data, onExplore, className = "" }) {
  const trendClass = data?.direction === "down" ? "splash-widget__trend--down" : "splash-widget__trend--up";

  return (
    <article className={`splash-widget${className ? ` ${className}` : ""}`}>
      <h3 className="splash-widget__title">
        Today&apos;s Insight
        <span className="splash-widget__accent" aria-hidden="true">
          ✦
        </span>
      </h3>
      <p className={`splash-widget__trend ${trendClass}`}>{data?.trend || "Revenue ↗ +12%"}</p>
      <p className="splash-widget__value">{data?.value || "AED 17.4M"}</p>
      <p className="splash-widget__desc">{data?.description || "Best month in Q1"}</p>
      <button type="button" className="splash-widget__cta" onClick={onExplore}>
        Explore →
      </button>
    </article>
  );
}
