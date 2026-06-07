export default function SkipButton({ label, onClick, className = "" }) {
  return (
    <button
      type="button"
      className={`splash-skip-btn${className ? ` ${className}` : ""}`}
      onClick={onClick}
    >
      {label}
    </button>
  );
}
