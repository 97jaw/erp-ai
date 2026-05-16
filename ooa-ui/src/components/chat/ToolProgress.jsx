export default function ToolProgress({ steps }) {
  if (!steps?.length) return null;

  const iconForStatus = (status) => {
    if (status === "done") return "✓";
    if (status === "failed") return "✗";
    if (status === "running") return "⟳";
    return "◯";
  };

  return (
    <div className="ooa-tool-progress" aria-live="polite">
      {steps.map((step) => (
        <div
          key={step.id}
          className={`ooa-tool-progress__step ooa-tool-progress__step--${step.status || "queued"}`}
        >
          <span className="ooa-tool-progress__icon" aria-hidden="true">
            {iconForStatus(step.status)}
          </span>
          <span>{step.label}</span>
        </div>
      ))}
    </div>
  );
}
