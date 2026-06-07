import { useEffect, useRef, useState } from "react";

export default function OutlookConnectModal({
  open,
  userEmail = "",
  onConnect,
  onLearnMore,
  onSkipToChat,
  onClose,
}) {
  const skipRef = useRef(null);
  const [email, setEmail] = useState(userEmail);
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (open) setEmail(userEmail || "");
  }, [open, userEmail]);

  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement;
    skipRef.current?.focus();
    const onKey = (event) => {
      if (event.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  const handleSubmit = (event) => {
    event.preventDefault();
    onConnect?.({ email: email.trim(), password });
  };

  return (
    <div
      className="splash-outlook-modal-backdrop"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose?.();
      }}
    >
      <div
        className="splash-outlook-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="splash-outlook-title"
      >
        <h2 id="splash-outlook-title" className="splash-outlook-modal__title">
          📧 Connect Outlook
        </h2>
        <p className="splash-outlook-modal__lead">
          Sync emails and unlock inbox insights. You can connect later from settings.
        </p>

        <form className="splash-outlook-modal__form" onSubmit={handleSubmit}>
          <label className="splash-outlook-modal__label" htmlFor="splash-outlook-email">
            Email
          </label>
          <input
            id="splash-outlook-email"
            className="splash-outlook-modal__input"
            type="email"
            autoComplete="email"
            placeholder="user@elrace.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />

          <label className="splash-outlook-modal__label" htmlFor="splash-outlook-password">
            Password / App Code
          </label>
          <input
            id="splash-outlook-password"
            className="splash-outlook-modal__input"
            type="password"
            autoComplete="off"
            placeholder="••••••••••••"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />

          <button type="submit" className="splash-connect-btn">
            Connect Securely →
          </button>
        </form>

        <p className="splash-outlook-modal__trust">
          🔒 Encrypted, never shared
          <button type="button" className="splash-outlook__link" onClick={onLearnMore}>
            What is this?
          </button>
        </p>

        <div className="splash-outlook-modal__footer">
          <button
            ref={skipRef}
            type="button"
            className="splash-skip-btn splash-outlook-modal__skip-main"
            onClick={onSkipToChat}
          >
            Skip → Open Chat
          </button>
        </div>
      </div>
    </div>
  );
}
