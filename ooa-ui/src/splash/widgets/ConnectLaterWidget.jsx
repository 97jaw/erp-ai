export default function ConnectLaterWidget({ onReconnect }) {
  return (
    <article className="splash-widget splash-connect-later">
      <h3 className="splash-widget__title">📧 Outlook</h3>
      <p className="splash-widget__desc">Skipped — connect later from settings or reopen below.</p>
      <button type="button" className="splash-widget__cta" onClick={onReconnect}>
        Connect Outlook →
      </button>
    </article>
  );
}
