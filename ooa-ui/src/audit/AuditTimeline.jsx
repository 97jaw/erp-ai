import AuditChangeEntry from "./AuditChangeEntry";

export default function AuditTimeline({ timeline = [], emptyMessage }) {
  if (!timeline.length) {
    return (
      <div className="ooa-audit-empty">
        {emptyMessage || "No changes recorded for this period."}
      </div>
    );
  }

  return (
    <section className="ooa-audit-timeline" aria-label="Change timeline">
      {timeline.map((entry, index) => (
        <AuditChangeEntry
          key={`${entry.date}-${entry.author}-${index}`}
          entry={entry}
          defaultExpanded={index === 0}
        />
      ))}
    </section>
  );
}
