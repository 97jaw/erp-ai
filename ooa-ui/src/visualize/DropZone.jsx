import { AnimatePresence } from "framer-motion";
import DroppedItem from "./DroppedItem";

export default function DropZone({
  items,
  isDraggingOver,
  isDraggingFromChat,
  lastDropAt,
  onDragOver,
  onDragLeave,
  onDrop,
  onRemoveItem,
  onClear,
}) {
  const showPulse = isDraggingOver && isDraggingFromChat;
  const showSuccess = lastDropAt && Date.now() - lastDropAt < 1200;

  return (
    <section
      className={[
        "ooa-viz-dropzone",
        isDraggingOver ? "ooa-viz-dropzone--active" : "",
        showPulse ? "ooa-viz-dropzone--pulse" : "",
        showSuccess ? "ooa-viz-dropzone--landed" : "",
        items.length ? "ooa-viz-dropzone--has-items" : "",
      ].filter(Boolean).join(" ")}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      aria-label="Drop chat responses to visualize"
    >
      <div className="ooa-viz-dropzone__inner">
        {items.length === 0 ? (
          <div className="ooa-viz-dropzone__empty">
            <span className="ooa-viz-dropzone__icon" aria-hidden="true">✦</span>
            <p className="ooa-viz-dropzone__title">
              {isDraggingOver ? "Drop to visualize" : "Drag a response here"}
            </p>
            <p className="ooa-viz-dropzone__hint">
              Grab any AI answer from the chat and drop it in this zone
            </p>
          </div>
        ) : (
          <>
            <div className="ooa-viz-dropzone__header">
              <span>{items.length} item{items.length === 1 ? "" : "s"} ready</span>
              <button type="button" className="ooa-viz-dropzone__clear" onClick={onClear}>
                Clear
              </button>
            </div>
            <AnimatePresence initial={false}>
              <div className="ooa-viz-dropzone__stack">
                {items.map((item, index) => (
                  <DroppedItem
                    key={item.id}
                    item={item}
                    index={index}
                    onRemove={onRemoveItem}
                  />
                ))}
              </div>
            </AnimatePresence>
          </>
        )}
      </div>
    </section>
  );
}
