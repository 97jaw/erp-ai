export default function VisualizeToggle({ open, itemCount, onToggle }) {
  if (open) {
    return (
      <button
        type="button"
        className="ooa-viz-rail__collapse"
        onClick={onToggle}
        title="Collapse Visualize panel (⌘V)"
        aria-label="Collapse Visualize panel"
      >
        ›
      </button>
    );
  }

  return (
    <button
      type="button"
      className="ooa-viz-rail"
      onClick={onToggle}
      title="Open Visualize (⌘V)"
      aria-label="Open Visualize panel"
    >
      <span className="ooa-viz-rail__glyph" aria-hidden="true">◊</span>
      <span className="ooa-viz-rail__label">Visualize</span>
      {itemCount > 0 ? (
        <span className="ooa-viz-rail__count">{itemCount}</span>
      ) : null}
    </button>
  );
}
