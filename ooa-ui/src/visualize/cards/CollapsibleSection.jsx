import { useEffect, useId, useState } from "react";

export default function CollapsibleSection({
  title,
  subtitle,
  badge,
  icon,
  defaultOpen = true,
  autoCollapseWhen = false,
  fill = false,
  children,
  className = "",
}) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = useId();
  const headerId = useId();

  useEffect(() => {
    setOpen(defaultOpen);
  }, [defaultOpen]);

  useEffect(() => {
    if (autoCollapseWhen) {
      setOpen(false);
    }
  }, [autoCollapseWhen]);

  if (!children) return null;

  const sectionClass = [
    "viz-collapse",
    fill ? "viz-collapse--fill" : "",
    open ? "viz-collapse--open" : "viz-collapse--closed",
    className,
  ].filter(Boolean).join(" ");

  const toggleLabel = open ? `Collapse ${title}` : `Expand ${title}`;

  return (
    <section className={sectionClass}>
      <button
        type="button"
        id={headerId}
        className="viz-collapse__header"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={toggleLabel}
        onClick={() => setOpen((prev) => !prev)}
      >
        {icon ? (
          <span className="viz-collapse__icon" aria-hidden="true">
            {icon}
          </span>
        ) : null}
        <span className="viz-collapse__header-text">
          <span className="viz-collapse__title">{title}</span>
          {subtitle ? <span className="viz-collapse__subtitle">{subtitle}</span> : null}
        </span>
        {badge ? <span className="viz-collapse__badge">{badge}</span> : null}
        <span className="viz-collapse__toggle" aria-hidden="true">
          {open ? "−" : "+"}
        </span>
      </button>
      {open ? (
        <div id={panelId} className="viz-collapse__body" role="region" aria-labelledby={headerId}>
          {children}
        </div>
      ) : null}
    </section>
  );
}
