export default function StatsBar() {
  return (
    <div className="splash-stats" aria-label="System status">
      <span className="splash-stats__item">247 queries today</span>
      <span className="splash-stats__item">18 reports generated</span>
      <span className="splash-stats__item">Connected to Odoo Live</span>
    </div>
  );
}
