export default function PendingWidget({ count = 3, subtitle, onReview, className = "" }) {
  return (
    <article className={`splash-widget${className ? ` ${className}` : ""}`}>
      <h3 className="splash-widget__title">Pending Approvals</h3>
      <p className="splash-widget__value splash-widget__value--pending">{count}</p>
      <p className="splash-widget__desc">
        {subtitle || "Invoices waiting review"}
      </p>
      <button type="button" className="splash-widget__cta" onClick={onReview}>
        Review →
      </button>
    </article>
  );
}
