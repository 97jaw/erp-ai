import { useCallback, useState } from "react";
import { motion } from "framer-motion";
import { IconClipboard, IconGrip } from "../common/MainIcons";
import { buildVisualizeDragPayload } from "../../visualize/dragPayload";
import { VISUALIZE_DRAG_MIME } from "../../visualize/constants";
import {
  detectTextDirection,
  hasRenderableVisualization,
  humanizeOutput,
  normalizeVisualization,
} from "../../utils/chat";
import StreamingMessageText from "./StreamingMessageText";
import VisualizationPanel from "../visualization/VisualizationPanel";
import VisualizationSkeleton from "../visualization/VisualizationSkeleton";
import SuggestionChips from "./SuggestionChips";
import TypingIndicator from "./TypingIndicator";
import ToolProgress from "./ToolProgress";

export default function MessageBubble({
  msg,
  pendingLabel,
  pendingVizType,
  toolSteps,
  parallaxOffset = 0,
  onSuggestion,
  onShowMoreSuggestions,
  loadingMoreSuggestions = false,
  language = "en",
  isStreaming = false,
  visualizeDragContext = null,
  onVisualizeDragStart,
  onVisualizeDragEnd,
}) {
  const [copied, setCopied] = useState(false);
  const [dragging, setDragging] = useState(false);

  const isUser = msg.role === "user";
  const preferDir = language?.startsWith("ar") ? "rtl" : "ltr";
  const rtl = !isUser && msg.id !== "welcome"
    ? detectTextDirection(msg.text, { prefer: preferDir }) === "rtl"
    : detectTextDirection(msg.text, { prefer: preferDir }) === "rtl";
  const visualization = hasRenderableVisualization(msg.visualization)
    ? normalizeVisualization(msg.visualization)
    : null;
  const displayText = isUser ? msg.text : humanizeOutput(msg.text);
  const showText = Boolean(displayText?.trim());
  const showPending = Boolean(pendingLabel) && !showText && !visualization && !isStreaming;
  const showSkeleton = Boolean(pendingVizType) && !visualization && !showPending;
  const depth = visualization ? 0.85 : msg.suggestions?.length ? 0.7 : 1;
  const parallaxShift = -(parallaxOffset || 0) * (1 - depth) * 0.04;

  const canDragToVisualize = Boolean(
    !isUser
    && visualizeDragContext
    && (showText || visualization)
    && !showPending
    && !showSkeleton,
  );

  const canCopy = Boolean(!isUser && showText && !showPending && !showSkeleton);
  const showToolbar = !isUser && (canCopy || canDragToVisualize);

  const handleCopy = useCallback(async () => {
    const text = String(msg.text || "").trim();
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked */
    }
  }, [msg.text]);

  const handleDragStart = useCallback((event) => {
    if (!canDragToVisualize) {
      event.preventDefault();
      return;
    }
    const payload = buildVisualizeDragPayload({
      queryId: visualizeDragContext.queryId,
      messageId: msg.id,
      question: visualizeDragContext.question,
      text: msg.text,
      visualization,
      vizType: visualization?.visual_type || pendingVizType,
      createdAt: visualizeDragContext.createdAt,
    });
    event.dataTransfer.setData(VISUALIZE_DRAG_MIME, JSON.stringify(payload));
    event.dataTransfer.setData("application/json", JSON.stringify(payload));
    event.dataTransfer.effectAllowed = "copy";
    setDragging(true);
    onVisualizeDragStart?.();
  }, [
    canDragToVisualize,
    visualizeDragContext,
    msg.id,
    msg.text,
    visualization,
    pendingVizType,
    onVisualizeDragStart,
  ]);

  const handleDragEnd = useCallback(() => {
    setDragging(false);
    onVisualizeDragEnd?.();
  }, [onVisualizeDragEnd]);

  return (
    <motion.div
      className={[
        "ooa-message",
        isUser ? "ooa-message--user" : "ooa-message--bot",
        dragging ? "ooa-message--dragging" : "",
      ].filter(Boolean).join(" ")}
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
        {showToolbar ? (
          <div className="ooa-message__toolbar" role="toolbar" aria-label="Message actions">
            {canCopy ? (
              <button
                type="button"
                className={`ooa-message__action${copied ? " ooa-message__action--success" : ""}`}
                onClick={handleCopy}
                aria-label={copied ? "Copied" : "Copy response"}
                title={copied ? "Copied" : "Copy"}
              >
                <IconClipboard size={16} />
              </button>
            ) : null}
            {canDragToVisualize ? (
              <span
                className="ooa-message__action ooa-message__action--drag"
                draggable
                onDragStart={handleDragStart}
                onDragEnd={handleDragEnd}
                role="button"
                tabIndex={0}
                aria-label="Drag to Visualize panel"
                title="Drag to Visualize"
              >
                <IconGrip size={16} />
              </span>
            ) : null}
          </div>
        ) : null}

        {showText || isStreaming ? (
          <div
            className={`ooa-bubble ${isUser ? "ooa-bubble--user" : "ooa-bubble--bot"}`}
            dir={isUser ? (rtl ? "rtl" : "ltr") : preferDir}
            style={{
              textAlign: rtl ? "right" : "left",
            }}
          >
            {isUser ? (
              <span className="ooa-bubble__text">{displayText}</span>
            ) : (
              <StreamingMessageText
                text={displayText}
                language={language}
                isStreaming={isStreaming}
              />
            )}
          </div>
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
          <SuggestionChips
            items={msg.suggestions}
            onSelect={onSuggestion}
            onShowMore={onShowMoreSuggestions}
            hasMore={msg.suggestionMeta?.has_more}
            loadingMore={loadingMoreSuggestions}
            language={language}
          />
        ) : null}
      </div>
    </motion.div>
  );
}
