import { useEffect, useRef } from "react";

export default function ComingSoonFeatureModal({ open, title, body, onClose }) {
  const closeRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement;
    closeRef.current?.focus();
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

  return (
    <div
      className="ooa-consent-backdrop"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose?.();
      }}
    >
      <div className="ooa-consent-modal" role="dialog" aria-modal="true" aria-labelledby="ooa-soon-title">
        <h2 id="ooa-soon-title" className="ooa-consent-modal__title">{title}</h2>
        <p className="ooa-consent-modal__body">{body}</p>
        <div className="ooa-consent-modal__actions">
          <button
            ref={closeRef}
            type="button"
            className="ooa-consent-modal__btn ooa-consent-modal__btn--ai"
            onClick={onClose}
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  );
}
