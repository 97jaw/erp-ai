import { motion } from "framer-motion";
import { SHOWCASE_FEATURES } from "../../utils/layoutContent";

export default function FeatureShowcase() {
  return (
    <motion.div
      className="ooa-welcome-screen__grid"
      initial="hidden"
      animate="visible"
      variants={{ visible: { transition: { staggerChildren: 0.05 } } }}
      aria-label="Capabilities overview"
    >
      {SHOWCASE_FEATURES.map((feature) => (
        <motion.div
          key={feature.id}
          className="ooa-feature-card ooa-feature-card--readonly"
          variants={{ hidden: { opacity: 0, y: 18 }, visible: { opacity: 1, y: 0 } }}
          aria-hidden="true"
        >
          <span className="ooa-feature-card__icon">{feature.icon}</span>
          <span className="ooa-feature-card__title">{feature.title}</span>
          <span className="ooa-feature-card__subtitle">{feature.subtitle}</span>
        </motion.div>
      ))}
    </motion.div>
  );
}
