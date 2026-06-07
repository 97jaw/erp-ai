import { useEffect, useMemo, useState } from "react";
import { buildInspectionLines } from "./buildInspectionLines";

export default function InspectionCard({ inspection, analyzing = false, embedded = false }) {
  const lines = useMemo(() => buildInspectionLines(inspection), [inspection]);
  const [visibleLines, setVisibleLines] = useState(0);

  useEffect(() => {
    setVisibleLines(0);
    if (!inspection) return undefined;

    const interval = window.setInterval(() => {
      setVisibleLines((prev) => {
        if (prev >= lines.length) {
          window.clearInterval(interval);
          return prev;
        }
        return prev + 1;
      });
    }, 140);

    return () => window.clearInterval(interval);
  }, [inspection, lines]);

  const showProgress = visibleLines >= lines.length && analyzing;
  const cardClass = embedded
    ? "viz-analysis-card viz-analysis-card--embedded inspection-card"
    : "viz-analysis-card inspection-card";

  return (
    <div className={cardClass}>
      {!embedded ? (
        <div className="viz-analysis-card__title">Analyzing your data…</div>
      ) : null}
      <div className="inspection-card__lines">
        {lines.slice(0, visibleLines).map((line) => (
          <div key={line} className="inspection-line fade-in">
            <span className="inspection-line__bullet">●</span>
            <span className="inspection-line__text">{line}</span>
          </div>
        ))}
      </div>
      {showProgress ? (
        <div className="inspection-card__progress">
          <div className="inspection-card__progress-bar">
            <span className="inspection-card__progress-fill" />
          </div>
          <span className="inspection-card__progress-label">Analyzing patterns…</span>
        </div>
      ) : null}
    </div>
  );
}
