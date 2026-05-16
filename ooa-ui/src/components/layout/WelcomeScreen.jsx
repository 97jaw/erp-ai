import { motion } from "framer-motion";
import FeatureShowcase from "./FeatureShowcase";

export default function WelcomeScreen({ onOpenSpotlight, onSeedQuery, compact = false }) {
  return (
    <section
      className={`ooa-welcome-screen ${compact ? "ooa-welcome-screen--compact" : ""}`}
      aria-label="Welcome"
      onClick={(event) => {
        if (event.target.closest("button")) return;
        onOpenSpotlight();
      }}
    >
      <motion.div
        className="ooa-welcome-screen__hero"
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45 }}
      >
        <motion.div
          className="ooa-welcome-screen__rule"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 0.8, delay: 0.1 }}
        />
        <h1 className="ooa-welcome-screen__title">
          {"Welcome to Elrace AI".split("").map((character, index) => (
            <motion.span
              key={`${character}-${index}`}
              className="ooa-welcome-screen__title-char"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.03, duration: 0.25 }}
            >
              {character === " " ? "\u00a0" : character}
            </motion.span>
          ))}
        </h1>
        <motion.p
          className="ooa-welcome-screen__subtitle"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.35, duration: 0.35 }}
        >
          Your Intelligent ERP Companion
        </motion.p>
        <motion.div
          className="ooa-welcome-screen__rule"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 0.8, delay: 0.2 }}
        />
      </motion.div>

      {!compact ? (
        <FeatureShowcase onSelectFeature={(feature) => onSeedQuery(feature.query)} />
      ) : (
        <p className="ooa-welcome-screen__quickstart">
          Ask about projects, financials, purchase orders, or reports. Start typing anywhere to open chat.
        </p>
      )}

      <button type="button" className="ooa-welcome-screen__cta" onClick={onOpenSpotlight}>
        {compact ? "Open chat" : "Start typing anywhere or click to chat"}
      </button>

      {!compact ? (
        <motion.div
          className="ooa-welcome-screen__dots"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          aria-hidden="true"
        >
          <span className="ooa-welcome-screen__dot ooa-welcome-screen__dot--active" />
          <span className="ooa-welcome-screen__dot" />
          <span className="ooa-welcome-screen__dot" />
          <span className="ooa-welcome-screen__dot" />
          <span className="ooa-welcome-screen__dot" />
        </motion.div>
      ) : null}
    </section>
  );
}
