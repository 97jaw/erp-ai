import { motion } from "framer-motion";
import { SHOWCASE_FEATURES } from "../../utils/layoutContent";

export default function FeatureShowcase({ onSelectFeature }) {
  return (
    <motion.div
      className="ooa-welcome-screen__grid"
      initial="hidden"
      animate="visible"
      variants={{ visible: { transition: { staggerChildren: 0.05 } } }}
    >
      {SHOWCASE_FEATURES.map((feature) => (
        <motion.button
          key={feature.id}
          type="button"
          className="ooa-feature-card"
          variants={{ hidden: { opacity: 0, y: 18 }, visible: { opacity: 1, y: 0 } }}
          whileHover={{ y: -8, scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => onSelectFeature?.(feature)}
        >
          <span className="ooa-feature-card__icon">{feature.icon}</span>
          <span className="ooa-feature-card__title">{feature.title}</span>
          <span className="ooa-feature-card__subtitle">{feature.subtitle}</span>
        </motion.button>
      ))}
    </motion.div>
  );
}
