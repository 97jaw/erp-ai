import { motion } from "framer-motion";
import { normalizeSuggestion } from "../../utils/chat";

export default function SuggestionChips({ items, onSelect }) {
  if (!items?.length) return null;

  const visible = items
    .map((item) => normalizeSuggestion(item))
    .filter((item) => item && item.length <= 90);

  if (!visible.length) return null;

  return (
    <motion.div
      className="ooa-suggestions"
      initial="hidden"
      animate="visible"
      variants={{
        hidden: {},
        visible: { transition: { staggerChildren: 0.05 } },
      }}
    >
      {visible.map((suggestion) => (
        <motion.button
          key={suggestion}
          type="button"
          className="ooa-suggestion-chip"
          variants={{
            hidden: { opacity: 0, y: 8 },
            visible: { opacity: 1, y: 0 },
          }}
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={() => onSelect(suggestion)}
        >
          <span aria-hidden="true">✦</span>
          {suggestion}
        </motion.button>
      ))}
    </motion.div>
  );
}
