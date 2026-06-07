export default function TrustIndicators({ isLoggedIn, reveal, awaitingReveal = false }) {
  if (!isLoggedIn) {
    return (
      <p className="splash-trust splash-trust--guest">
        Sign in with your Elrace File ID to unlock live insights, approvals, and chat.
      </p>
    );
  }

  return (
    <div
      className={`splash-trust${
        reveal ? " splash-pop-in splash-pop-in--delay-7" : awaitingReveal ? " splash-await-reveal" : ""
      }`}
      aria-label="Trust indicators"
    >
      <p className="splash-trust__hint">Connect Outlook to unlock inbox insights.</p>
      <div className="splash-trust__stats">
        <span className="splash-trust__stat">247 queries today</span>
        <span className="splash-trust__stat">18 reports generated</span>
        <span className="splash-trust__stat">Connected to Odoo Live</span>
      </div>
    </div>
  );
}
