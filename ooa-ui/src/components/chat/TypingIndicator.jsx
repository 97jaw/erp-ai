import { motion } from "framer-motion";

export default function TypingIndicator({ label }) {
  return (
    <motion.div
      className="ooa-typing"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <span className="ooa-typing__label">{label || "Preparing your answer..."}</span>
      {[0, 0.2, 0.4].map((delay) => (
        <span key={delay} className="ooa-typing__dot" style={{ animationDelay: `${delay}s` }} />
      ))}
    </motion.div>
  );
}
