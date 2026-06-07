import "./cards/analysisCards.css";
import DropZone from "./DropZone";
import VisualizeToggle from "./VisualizeToggle";
import VisualizeAgent from "./VisualizeAgent";

export default function VisualizePanel({
  open,
  borderState = "inactive",
  droppedItems,
  isDraggingOver,
  isDraggingFromChat,
  lastDropAt,
  chatSessionId,
  onToggle,
  onClose,
  onDragOver,
  onDragLeave,
  onDrop,
  onRemoveItem,
  onClear,
}) {
  const wrapClass = [
    "ooa-visualize-panel-wrap",
    open ? "ooa-visualize-panel-wrap--open" : "ooa-visualize-panel-wrap--closed",
    borderState === "active" ? "ooa-visualize-panel-wrap--active" : "",
    borderState === "processing" ? "ooa-visualize-panel-wrap--processing" : "",
  ].filter(Boolean).join(" ");

  return (
    <>
      <VisualizeToggle
        open={open}
        itemCount={droppedItems.length}
        onToggle={onToggle}
      />

      <aside className={wrapClass} aria-label="Visualize agent panel" aria-hidden={!open}>
        <div className="ooa-visualize-panel">
          <header className="ooa-visualize-panel__header">
            <div className="ooa-visualize-panel__title-wrap">
              <div className="ooa-visualize-panel__title">
                <span className="ooa-visualize-panel__mark" aria-hidden="true">◊</span>
                Visualize Agent
              </div>
              <span className="ooa-visualize-panel__hint">
                Drag responses · ⌘V toggle · PDF or Excel
              </span>
            </div>
            <button
              type="button"
              className="ooa-visualize-panel__close"
              onClick={onClose}
              aria-label="Close Visualize panel"
            >
              ×
            </button>
          </header>

          {open ? (
            <>
              <DropZone
                items={droppedItems}
                isDraggingOver={isDraggingOver}
                isDraggingFromChat={isDraggingFromChat}
                lastDropAt={lastDropAt}
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                onDrop={onDrop}
                onRemoveItem={onRemoveItem}
                onClear={onClear}
              />

              <VisualizeAgent
                droppedItems={droppedItems}
                chatSessionId={chatSessionId}
              />
            </>
          ) : null}
        </div>
      </aside>
    </>
  );
}
