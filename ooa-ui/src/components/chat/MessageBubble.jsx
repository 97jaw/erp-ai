import { motion } from "framer-motion";
import { isArabic, hasRenderableVisualization, normalizeVisualization } from "../../utils/chat";
import VisualizationPanel from "../visualization/VisualizationPanel";
import VisualizationSkeleton from "../visualization/VisualizationSkeleton";
import SuggestionChips from "./SuggestionChips";
import TypingIndicator from "./TypingIndicator";
import ToolProgress from "./ToolProgress";

export default function MessageBubble({ msg, pendingLabel, pendingVizType, toolSteps, parallaxOffset = 0, onSuggestion }) {
  const isUser = msg.role === "user";
  const rtl = msg.id === "welcome" ? false : isArabic(msg.text);
  const visualization = hasRenderableVisualization(msg.visualization)
    ? normalizeVisualization(msg.visualization)
    : null;
  const showText = Boolean(msg.text?.trim());
  const showPending = Boolean(pendingLabel) && !showText && !visualization;
  const showSkeleton = Boolean(pendingVizType) && !visualization && !showPending;
  const depth = visualization ? 0.85 : msg.suggestions?.length ? 0.7 : 1;
  const parallaxShift = -(parallaxOffset || 0) * (1 - depth) * 0.04;

  return (
    <motion.div
      className={`ooa-message ${isUser ? "ooa-message--user" : "ooa-message--bot"}`}
      initial={{ opacity: 0, y: 14, x: isUser ? 18 : -18 }}
      animate={{ opacity: 1, y: parallaxShift, x: 0 }}
      transition={{ type: "spring", stiffness: 320, damping: 26 }}
    >
      {!isUser ? (
        <motion.div
          className="ooa-message__avatar"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: "spring", stiffness: 420, damping: 18 }}
        >
          <span>◈</span>
        </motion.div>
      ) : null}

      <div className="ooa-message__content">
        {showText ? (
          <motion.div
            className={`ooa-bubble ${isUser ? "ooa-bubble--user" : "ooa-bubble--bot"}`}
            style={{
              direction: rtl ? "rtl" : "ltr",
              textAlign: rtl ? "right" : "left",
            }}
          >
            {msg.text}
            {showPending ? <span className="ooa-bubble__cursor" /> : null}
          </motion.div>
        ) : null}

        {showPending ? <TypingIndicator label={pendingLabel} /> : null}
        {toolSteps?.length ? <ToolProgress steps={toolSteps} /> : null}
        {showSkeleton ? (
          <motion.div layout initial={{ opacity: 0.7 }} animate={{ opacity: 1 }}>
            <VisualizationSkeleton type={pendingVizType} />
          </motion.div>
        ) : null}
        {visualization ? (
          <motion.div layout initial={{ opacity: 0.85, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <VisualizationPanel viz={visualization} />
          </motion.div>
        ) : null}
        {msg.suggestions?.length ? (
          <SuggestionChips items={msg.suggestions} onSelect={onSuggestion} />
        ) : null}
      </div>
    </motion.div>
  );
}
