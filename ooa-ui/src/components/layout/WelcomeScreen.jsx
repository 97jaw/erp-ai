import FeatureShowcase from "./FeatureShowcase";

export default function WelcomeScreen({ onOpenSpotlight, onSeedQuery, compact = false }) {
  return (
    <section
      className={`ooa-welcome-screen ${compact ? "ooa-welcome-screen--compact" : ""}`}
      aria-label="Welcome"
      onClick={(event) => {
        if (event.target.closest("button, .ooa-feature-card")) return;
        onOpenSpotlight?.();
      }}
    >
      <div className="ooa-welcome-screen__hero">
        <div className="ooa-welcome-screen__rule" />
        <h1 className="ooa-welcome-screen__title">Welcome to Elrace AI</h1>
        <p className="ooa-welcome-screen__subtitle">Your intelligent ERP companion</p>
        <div className="ooa-welcome-screen__rule" />
      </div>

      {!compact ? (
        <FeatureShowcase />
      ) : (
        <p className="ooa-welcome-screen__quickstart">
          Ask about projects, finances, purchase orders, or reports. Start typing below — or press
          any key.
        </p>
      )}

      {!compact ? (
        <button type="button" className="ooa-welcome-screen__cta" onClick={() => onOpenSpotlight?.()}>
          Start typing anywhere or click to chat
        </button>
      ) : null}

      {!compact ? (
        <div className="ooa-welcome-screen__dots" aria-hidden="true">
          <span className="ooa-welcome-screen__dot ooa-welcome-screen__dot--active" />
          <span className="ooa-welcome-screen__dot" />
          <span className="ooa-welcome-screen__dot" />
          <span className="ooa-welcome-screen__dot" />
          <span className="ooa-welcome-screen__dot" />
        </div>
      ) : null}
    </section>
  );
}
