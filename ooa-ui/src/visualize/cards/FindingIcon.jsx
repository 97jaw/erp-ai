const ICONS = {
  trend_up: "↗",
  trend_down: "↘",
  warning: "⚠",
  concentration: "◉",
  outlier: "⊙",
  info: "※",
};

export default function FindingIcon({ name }) {
  return (
    <span className="viz-finding-icon" aria-hidden="true">
      {ICONS[name] || "•"}
    </span>
  );
}
