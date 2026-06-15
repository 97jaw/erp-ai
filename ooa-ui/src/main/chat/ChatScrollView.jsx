import { useCallback, useEffect, useRef, useState } from "react";
import MessageBubble from "../../components/chat/MessageBubble";
import ClarificationCard from "../../components/chat/ClarificationCard";
import { formatDateSeparator, shouldShowDateSeparator } from "./chatDates";

export default function ChatScrollView({
  queries,
  activeQueryId,
  loading,
  loadingStage,
  pendingVizType,
  toolSteps,
  language,
  onSuggestion,
  onUiBlockAction,
  onClarificationSelect,
  onClarificationSkip,
  onShowMoreSuggestions,
  loadingMoreSuggestions,
  onVisualizeDragStart,
  onVisualizeDragEnd,
  onSendToVisualize,
  onJumpToLatest,
}) {
  const scrollRef = useRef(null);
  const [pinnedToBottom, setPinnedToBottom] = useState(true);

  const chronological = [...queries].reverse();

  const scrollToBottom = useCallback((behavior = "smooth") => {
    const node = scrollRef.current;
    if (!node) return;
    node.scrollTo({ top: node.scrollHeight, behavior });
  }, []);

  useEffect(() => {
    if (pinnedToBottom) scrollToBottom(queries.length > 1 ? "smooth" : "auto");
  }, [queries, loading, pinnedToBottom, scrollToBottom]);

  const handleScroll = () => {
    const node = scrollRef.current;
    if (!node) return;
    const distance = node.scrollHeight - node.scrollTop - node.clientHeight;
    setPinnedToBottom(distance < 80);
  };

  return (
    <section className="ooa-chat-scroll" aria-live="polite">
      <div
        ref={scrollRef}
        className="ooa-chat-scroll__viewport"
        onScroll={handleScroll}
      >
        {chronological.map((query, index) => {
          const visualizeDragContext = {
            queryId: query.id,
            question: query.question,
            createdAt: query.createdAt,
          };
          const userMessage = {
            id: `${query.id}-user`,
            role: "user",
            text: query.question,
          };
          const awaitingClarification =
            query.status === "awaiting_clarification"
            || Boolean(query.response?.clarification);
          const botMessage = {
            id: `${query.id}-bot`,
            role: "bot",
            text: query.response?.text || "",
            visualization: query.response?.visualization || null,
            suggestions: query.response?.suggestions || [],
            suggestionDetails: query.response?.suggestionDetails || null,
            suggestionMeta: query.response?.suggestionMeta || null,
            uiBlocks: query.response?.uiBlocks || [],
          };
          const isActive = query.id === activeQueryId;
          const showPending = isActive && loading;

          return (
            <article
              key={query.id}
              className={`ooa-chat-thread${isActive ? " ooa-chat-thread--active" : ""}`}
              id={`query-${query.id}`}
            >
              {shouldShowDateSeparator(chronological, index) ? (
                <div className="ooa-chat-scroll__date">
                  {formatDateSeparator(query.createdAt)}
                </div>
              ) : null}
              <div className="ooa-chat-thread__query">
                {!query.isWelcome && query.question ? (
                  <MessageBubble msg={userMessage} onSuggestion={onSuggestion} />
                ) : null}
              </div>
              <div
                className="ooa-response-card"
                dir={language?.startsWith("ar") ? "auto" : "ltr"}
              >
                {awaitingClarification ? (
                  <ClarificationCard
                    clarification={query.response?.clarification}
                    originalQuery={query.question}
                    onSelect={onClarificationSelect}
                    onSkip={onClarificationSkip}
                  />
                ) : (
                  <MessageBubble
                    msg={botMessage}
                    pendingLabel={showPending ? loadingStage : null}
                    pendingVizType={showPending ? pendingVizType : null}
                    toolSteps={showPending ? toolSteps : null}
                    isStreaming={showPending && Boolean(botMessage.text?.trim())}
                    onSuggestion={(label) => onSuggestion?.(label, query.id)}
                    onUiBlockAction={(action) => onUiBlockAction?.(action, query)}
                    onShowMoreSuggestions={
                      isActive ? () => onShowMoreSuggestions?.(query.id) : undefined
                    }
                    loadingMoreSuggestions={isActive && loadingMoreSuggestions}
                    language={language}
                    visualizeDragContext={visualizeDragContext}
                    onVisualizeDragStart={onVisualizeDragStart}
                    onVisualizeDragEnd={onVisualizeDragEnd}
                    onSendToVisualize={onSendToVisualize}
                  />
                )}
              </div>
            </article>
          );
        })}
      </div>

      {!pinnedToBottom ? (
        <button
          type="button"
          className="ooa-chat-scroll__new-pill"
          onClick={() => {
            scrollToBottom("smooth");
            onJumpToLatest?.();
          }}
        >
          ↓ New response below
        </button>
      ) : null}
    </section>
  );
}
