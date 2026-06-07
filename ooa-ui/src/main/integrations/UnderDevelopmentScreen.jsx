import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { getIntegration } from "./integrationConfig";
import { INTEGRATION_CONTENT } from "./integrationContent";

export default function UnderDevelopmentScreen({ serviceId }) {
  const navigate = useNavigate();
  const integration = getIntegration(serviceId);
  const content = INTEGRATION_CONTENT[serviceId];
  const [feedback, setFeedback] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [notifyEmail, setNotifyEmail] = useState("");

  if (!integration || !content) {
    return (
      <main className="ooa-integration-page" id="ooa-chat-main">
        <p className="ooa-integration-page__error">Integration not found.</p>
        <button type="button" className="ooa-integration-page__btn" onClick={() => navigate("/")}>
          Back to Chat
        </button>
      </main>
    );
  }

  return (
    <main className="ooa-integration-page" id="ooa-chat-main">
      <div className="ooa-integration-page__hero">
        <span className="ooa-integration-page__icon" aria-hidden="true">
          {integration.icon}
        </span>
        <h1 className="ooa-integration-page__title">{content.title}</h1>
      </div>

      <section className="ooa-integration-page__banner" aria-label="Status">
        <h2>Under Development</h2>
        <p>
          This integration is being built. Estimated release: {content.release}
        </p>
      </section>

      <section className="ooa-integration-page__features">
        <h3>What&apos;s Coming</h3>
        <ul>
          {content.features.map((feature) => (
            <li key={feature.title}>
              <span className="ooa-integration-page__feature-mark" aria-hidden="true">
                ✦
              </span>
              <div>
                <strong>{feature.title}</strong>
                <p>{feature.description}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="ooa-integration-page__notify">
        <h3>Get Notified When Ready</h3>
        <div className="ooa-integration-page__row">
          <input
            type="email"
            className="ooa-integration-page__input"
            placeholder="you@elrace.com"
            value={notifyEmail}
            onChange={(event) => setNotifyEmail(event.target.value)}
          />
          <button
            type="button"
            className="ooa-integration-page__btn ooa-integration-page__btn--primary"
            onClick={() => setSubmitted(true)}
          >
            Notify Me
          </button>
        </div>
        {submitted ? (
          <p className="ooa-integration-page__success">Thanks — we&apos;ll email you when this ships.</p>
        ) : null}
      </section>

      <section className="ooa-integration-page__feedback">
        <h3>Feedback</h3>
        <p>What would you like this integration to do?</p>
        <textarea
          className="ooa-integration-page__textarea"
          rows={4}
          value={feedback}
          onChange={(event) => setFeedback(event.target.value)}
          placeholder="Describe your ideal workflow…"
        />
        <button
          type="button"
          className="ooa-integration-page__btn"
          disabled={!feedback.trim()}
          onClick={() => {
            setFeedback("");
            setSubmitted(true);
          }}
        >
          Submit Feedback
        </button>
      </section>
    </main>
  );
}
