import { motion } from "framer-motion";

export default function GlassButton({
  children,
  className = "",
  primary = false,
  icon = false,
  ...props
}) {
  const classes = [
    "ooa-glass-button",
    primary ? "ooa-glass-button--primary" : "",
    icon ? "ooa-glass-button--icon" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <motion.button
      type="button"
      className={classes}
      whileHover={{ scale: props.disabled ? 1 : 1.03 }}
      whileTap={{ scale: props.disabled ? 1 : 0.96 }}
      {...props}
    >
      {children}
    </motion.button>
  );
}
