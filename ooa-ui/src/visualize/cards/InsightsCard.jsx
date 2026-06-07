import { useEffect, useState } from "react";
import FindingIcon from "./FindingIcon";

export default function InsightsCard({ findings = [], complete = false, embedded = false }) {
  const [revealed, setRevealed] = useState(0);

  useEffect(() => {
    setRevealed(0);
    if (!findings.length) return undefined;
    const interval = window.setInterval(() => {
      setRevealed((prev) => {
        if (prev >= findings.length) {
          window.clearInterval(interval);
          return prev;
        }
        return prev + 1;
      });
    }, 200);
    return () => window.clearInterval(interval);
  }, [findings]);

  if (!findings.length && !complete) return null;

  const cardClass = embedded
    ? "viz-analysis-card viz-analysis-card--embedded insights-card"
    : "viz-analysis-card insights-card";

  return (
    <div className={cardClass}>
      {!embedded ? (
        <div className="viz-analysis-card__title">
          {complete ? "Analysis complete ✓" : "Key findings"}
        </div>
      ) : null}
      {findings.length ? (
        <div className="insights-card__findings">
          {!embedded ? <div className="viz-analysis-card__subtitle">Key findings</div> : null}
          {findings.slice(0, revealed).map((finding, index) => (
            <div
              key={`${finding.text}-${index}`}
              className={`finding fade-in finding-${finding.color || "blue"}`}
            >
              <FindingIcon name={finding.icon} />
              <span className="finding__text">{finding.text}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="insights-card__empty">No strong patterns detected — a standard report still works well.</p>
      )}
    </div>
  );
}
