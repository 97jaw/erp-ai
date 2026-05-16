import { motion } from "framer-motion";

export default function Logo({ subtitle = "Elrace ERP Intelligence" }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
      style={{ display: "flex", alignItems: "center", gap: 12 }}
    >
      <motion.span
        initial={{ scale: 0, rotate: -180 }}
        animate={{ scale: 1, rotate: 0 }}
        transition={{ duration: 0.8, ease: "backOut" }}
        style={{
          fontSize: 28,
          color: "var(--ooa-gold)",
          lineHeight: 1,
          textShadow: "0 0 20px color-mix(in srgb, var(--ooa-gold) 40%, transparent)",
        }}
      >
        ◈
      </motion.span>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.5 }}
      >
        <motion.div style={{ fontSize: 16, fontWeight: 600, letterSpacing: "0.02em" }}>
          Odoo Omni-Agent
        </motion.div>
        <motion.div
          style={{
            fontSize: 11,
            color: "var(--ooa-text-muted)",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          {subtitle}
        </motion.div>
      </motion.div>
    </motion.div>
  );
}
