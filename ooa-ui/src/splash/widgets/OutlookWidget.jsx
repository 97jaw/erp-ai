import { useState } from "react";

export default function OutlookWidget({ defaultEmail = "", onConnect, onLearnMore, onSkip }) {
  const [email, setEmail] = useState(defaultEmail);
  const [password, setPassword] = useState("");

  const handleSubmit = (event) => {
    event.preventDefault();
    onConnect?.({ email: email.trim(), password });
  };

  return (
    <article className="splash-widget splash-outlook">
      <h3 className="splash-widget__title">📧 Connect Outlook</h3>
      <p className="splash-widget__desc">
        Sync emails, get insights from your inbox.
      </p>

      <form className="splash-outlook__form" onSubmit={handleSubmit}>
        <label className="splash-outlook__field" htmlFor="splash-outlook-email">
          Email
        </label>
        <input
          id="splash-outlook-email"
          className="splash-outlook__input"
          type="email"
          autoComplete="email"
          placeholder="user@elrace.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />

        <label className="splash-outlook__field" htmlFor="splash-outlook-password">
          Password / App Code
        </label>
        <input
          id="splash-outlook-password"
          className="splash-outlook__input"
          type="password"
          autoComplete="off"
          placeholder="••••••••••••"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />

        <div className="splash-outlook__actions">
          <button type="submit" className="splash-connect-btn">
            Connect Securely →
          </button>
          {onSkip ? (
            <button type="button" className="splash-outlook__skip" onClick={onSkip}>
              Skip →
            </button>
          ) : null}
        </div>
      </form>

      <p className="splash-outlook__trust">
        🔒 Encrypted, never shared
        <button type="button" className="splash-outlook__link" onClick={onLearnMore}>
          What is this?
        </button>
      </p>
    </article>
  );
}
