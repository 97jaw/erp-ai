import { useEffect, useRef } from "react";

export default function ComingSoonModal({ open, title, body, onClose }) {
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
      className="splash-modal-backdrop"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose?.();
      }}
    >
      <div
        className="splash-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="splash-modal-title"
      >
        <h2 id="splash-modal-title" className="splash-modal__title">
          {title}
        </h2>
        <p className="splash-modal__body">{body}</p>
        <div className="splash-modal__actions">
          <button
            ref={closeRef}
            type="button"
            className="splash-modal__btn splash-modal__btn--primary"
            onClick={onClose}
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  );
}
