import { useEffect, useRef } from "react";

export default function DeepThinkConsentModal({ open, mode = "send", onConfirm, onCancel }) {
  const confirmRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement;
    confirmRef.current?.focus();
    const onKey = (event) => {
      if (event.key === "Escape") onCancel?.();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [open, onCancel]);

  if (!open) return null;

  const title = mode === "enable" ? "Enable Deep Think?" : "Search with Deep Think?";
  const body =
    mode === "enable"
      ? "Deep Think pulls live figures from Odoo and may take longer. Enable it for your next message?"
      : "This query will run in Deep Think mode — live Odoo data, orchestrated tools, and a longer wait. Proceed?";

  return (
    <div
      className="ooa-consent-backdrop"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) onCancel?.();
      }}
    >
      <div
        className="ooa-consent-modal ooa-consent-modal--deepthink"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ooa-deepthink-consent-title"
      >
        <h2 id="ooa-deepthink-consent-title" className="ooa-consent-modal__title">
          {title}
        </h2>
        <p className="ooa-consent-modal__body">{body}</p>
        <div className="ooa-consent-modal__actions">
          <button type="button" className="ooa-consent-modal__btn" onClick={onCancel}>
            Cancel
          </button>
          <button
            ref={confirmRef}
            type="button"
            className="ooa-consent-modal__btn ooa-consent-modal__btn--ai"
            onClick={onConfirm}
          >
            Allow &amp; proceed
          </button>
        </div>
      </div>
    </div>
  );
}
