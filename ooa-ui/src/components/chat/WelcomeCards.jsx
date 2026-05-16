import { motion } from "framer-motion";
import { WELCOME_CARDS } from "../../utils/chat";

export default function WelcomeCards({ onSelect }) {
  return (
    <motion.div
      className="ooa-welcome-grid"
      initial="hidden"
      animate="visible"
      variants={{
        hidden: {},
        visible: { transition: { staggerChildren: 0.08 } },
      }}
    >
      {WELCOME_CARDS.map((card) => (
        <motion.button
          key={card.title}
          type="button"
          className="ooa-welcome-card"
          variants={{
            hidden: { opacity: 0, y: 16 },
            visible: { opacity: 1, y: 0 },
          }}
          whileHover={{ y: -3, scale: 1.01 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => onSelect(card.query)}
        >
          <span className="ooa-welcome-card__icon">{card.icon}</span>
          <span className="ooa-welcome-card__title">{card.title}</span>
          <span className="ooa-welcome-card__subtitle">{card.subtitle}</span>
        </motion.button>
      ))}
    </motion.div>
  );
}
