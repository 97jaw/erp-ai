export default function InsightCallouts({ insights = [] }) {
  if (!insights.length) return null;

  return (
    <div className="ooa-pe-insights">
      {insights.map((insight, index) => (
        <div
          key={`${insight.title}-${index}`}
          className={`ooa-pe-insight ooa-pe-insight--${insight.severity || "info"}`}
        >
          <div className="ooa-pe-insight__title">{insight.title}</div>
          <div className="ooa-pe-insight__message">{insight.message}</div>
        </div>
      ))}
    </div>
  );
}
