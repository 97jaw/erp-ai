import { motion } from "framer-motion";

export default function GlassCard({ className = "", premium = false, ...props }) {
  const classes = ["ooa-glass-card", premium ? "ooa-glass-card--premium" : "", className]
    .filter(Boolean)
    .join(" ");

  return <motion.div className={classes} {...props} />;
}
