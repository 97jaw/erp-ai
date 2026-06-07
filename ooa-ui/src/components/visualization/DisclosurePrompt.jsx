import { motion } from "framer-motion";

export default function DisclosurePrompt({
  label = "Would you like the detailed breakdown?",
  expandLabel = "See details",
  onExpand,
  onDismiss,
}) {
  return (
    <motion.div
      className="ooa-disclosure-prompt"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.15 }}
    >
      <p className="ooa-disclosure-prompt__text">{label}</p>
      <motion.div className="ooa-disclosure-prompt__actions">
        <button type="button" className="ooa-disclosure-prompt__primary" onClick={onExpand}>
          {expandLabel}
        </button>
        <button type="button" className="ooa-disclosure-prompt__secondary" onClick={onDismiss}>
          No thanks
        </button>
      </motion.div>
    </motion.div>
  );
}
