import { motion } from "framer-motion";
import { WELCOME_CARDS } from "../../utils/chat";

export default function WelcomeCards() {
  return (
    <motion.div
      className="ooa-welcome-grid"
      initial="hidden"
      animate="visible"
      variants={{
        hidden: {},
        visible: { transition: { staggerChildren: 0.08 } },
      }}
      aria-label="Capabilities overview"
    >
      {WELCOME_CARDS.map((card) => (
        <motion.div
          key={card.title}
          className="ooa-welcome-card ooa-welcome-card--readonly"
          variants={{
            hidden: { opacity: 0, y: 16 },
            visible: { opacity: 1, y: 0 },
          }}
          aria-hidden="true"
        >
          <span className="ooa-welcome-card__icon">{card.icon}</span>
          <span className="ooa-welcome-card__title">{card.title}</span>
          <span className="ooa-welcome-card__subtitle">{card.subtitle}</span>
        </motion.div>
      ))}
    </motion.div>
  );
}
