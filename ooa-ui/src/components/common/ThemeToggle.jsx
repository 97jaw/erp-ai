import { motion } from "framer-motion";
import { useTheme } from "../../theme/ThemeProvider";
import { sound } from "./SoundManager";

export default function ThemeToggle() {
  const { themeName, toggleTheme } = useTheme();

  return (
    <motion.button
      type="button"
      className="ooa-glass-button"
      onClick={() => {
        toggleTheme();
        sound.play("theme-toggle", { volume: 0.35 });
      }}
      aria-label={`Switch to ${themeName === "blackbat" ? "STARLIGHT" : "BLACKBAT"} theme`}
      whileTap={{ scale: 0.95 }}
      animate={{ rotateY: themeName === "blackbat" ? 0 : 180 }}
      transition={{ duration: 0.6 }}
      style={{
        width: 42,
        height: 42,
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 18,
      }}
    >
      {themeName === "blackbat" ? "🌙" : "☀️"}
    </motion.button>
  );
}
