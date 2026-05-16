import { motion } from "framer-motion";
import Logo from "../common/Logo";
import { buildWelcomeMessage } from "../../utils/chat";
import SuggestionChips from "./SuggestionChips";
import WelcomeCards from "./WelcomeCards";

export default function IdleWelcome({ user, suggestions, onSelect }) {
  const greeting = buildWelcomeMessage(user);
  const [englishBlock, arabicBlock] = greeting.includes("\n\nمرحباً")
    ? greeting.split("\n\nمرحباً")
    : [greeting, ""];

  return (
    <section className="ooa-idle-welcome" aria-label="Welcome">
      <Logo subtitle="Elrace AI" />
      <motion.div
        className="ooa-idle-welcome__intro"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
      >
        <p className="ooa-idle-welcome__greeting ooa-idle-welcome__greeting--en">{englishBlock.trim()}</p>
        {arabicBlock ? (
          <p className="ooa-idle-welcome__greeting ooa-idle-welcome__greeting--ar" dir="rtl">
            {`مرحباً${arabicBlock}`.trim()}
          </p>
        ) : null}
      </motion.div>
      <WelcomeCards onSelect={onSelect} />
      <SuggestionChips items={suggestions} onSelect={onSelect} />
    </section>
  );
}
