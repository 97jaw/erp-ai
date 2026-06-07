import { motion } from "framer-motion";
import { labelForDroppedItem } from "./dragPayload";

export default function DroppedItem({ item, index, onRemove }) {
  const label = labelForDroppedItem(item);
  const badge = item.vizType ? item.vizType.replace(/_/g, " ") : "Response";

  return (
    <div
      className="ooa-viz-dropped-item"
      layout
      initial={{ opacity: 0, scale: 0.92, y: 8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.9 }}
      transition={{ type: "spring", stiffness: 420, damping: 28 }}
    >
      <span className="ooa-viz-dropped-item__index">{index + 1}</span>
      <div className="ooa-viz-dropped-item__body">
        <span className="ooa-viz-dropped-item__title">{label}</span>
        <span className="ooa-viz-dropped-item__badge">{badge}</span>
      </div>
      <button
        type="button"
        className="ooa-viz-dropped-item__remove"
        title="Remove"
        onClick={() => onRemove(item.id)}
      >
        ×
      </button>
    </div>
  );
}
