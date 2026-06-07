import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import ThemeToggle from "../common/ThemeToggle";
import ProfileMenu from "./ProfileMenu";

const CHROME_IDLE_MS = 5000;
const CHROME_PROXIMITY_PX = 72;

export default function FloatingChrome({
  user,
  onLogout,
  onClearConversation,
  soundEnabled,
  volume,
  onToggleSound,
  onVolumeChange,
}) {
  const [chromeActive, setChromeActive] = useState(true);

  useEffect(() => {
    const timer = window.setTimeout(() => setChromeActive(false), CHROME_IDLE_MS);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    const onMove = (event) => {
      const nearTopRight = event.clientX > window.innerWidth - CHROME_PROXIMITY_PX
        && event.clientY < CHROME_PROXIMITY_PX + 48;
      const nearTopLeft = event.clientX < CHROME_PROXIMITY_PX
        && event.clientY < CHROME_PROXIMITY_PX + 48;
      if (nearTopRight || nearTopLeft) {
        setChromeActive(true);
      }
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, []);

  return (
    <>
      <motion.div
        className={`ooa-floating-chrome ooa-floating-chrome--theme ${chromeActive ? "is-active" : "is-idle"}`}
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: chromeActive ? 1 : 0.12 }}
        transition={{ duration: 0.35 }}
        onMouseEnter={() => setChromeActive(true)}
      >
        <ThemeToggle />
      </motion.div>

      <motion.div
        className={`ooa-floating-chrome ooa-floating-chrome--profile ${chromeActive ? "is-active" : "is-idle"}`}
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: chromeActive ? 1 : 0.12 }}
        transition={{ duration: 0.35, delay: 0.05 }}
        onMouseEnter={() => setChromeActive(true)}
      >
        <ProfileMenu
          user={user}
          soundEnabled={soundEnabled}
          volume={volume}
          onToggleSound={onToggleSound}
          onVolumeChange={onVolumeChange}
          onClearConversation={onClearConversation}
        />
        <button type="button" className="ooa-glass-button" onClick={onLogout}>
          Logout
        </button>
      </motion.div>
    </>
  );
}
