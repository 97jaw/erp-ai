export default function FeatureTeaserWidget({ icon, title, description, delay = 0 }) {
  return (
    <article
      className="splash-widget splash-teaser"
      style={{ "--splash-stagger": `${delay}ms` }}
    >
      <h3 className="splash-widget__title">
        <span aria-hidden="true">{icon}</span> {title}
      </h3>
      <p className="splash-widget__desc">{description}</p>
    </article>
  );
}
