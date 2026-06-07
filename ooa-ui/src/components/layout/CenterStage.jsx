import MessageBubble from "../chat/MessageBubble";
import ClarificationCard from "../chat/ClarificationCard";

export default function CenterStage({
  query,
  loading,
  loadingStage,
  pendingVizType,
  toolSteps,
  onSuggestion,
  onClarificationSelect,
  onClarificationSkip,
  onShowMoreSuggestions,
  loadingMoreSuggestions,
  language,
  onVisualizeDragStart,
  onVisualizeDragEnd,
}) {
  if (!query) return null;

  const visualizeDragContext = {
    queryId: query.id,
    question: query.question,
    createdAt: query.createdAt,
  };

  const userMessage = {
    id: `${query.id}-user`,
    role: "user",
    text: query.question,
    visualization: null,
    suggestions: [],
  };

  const awaitingClarification = query.status === "awaiting_clarification"
    || Boolean(query.response?.clarification);

  const botMessage = {
    id: `${query.id}-bot`,
    role: "bot",
    text: query.response?.text || "",
    visualization: query.response?.visualization || null,
    suggestions: query.response?.suggestions || [],
    suggestionMeta: query.response?.suggestionMeta || null,
  };

  return (
    <section className="ooa-center-stage" aria-live="polite">
      <div className="ooa-center-stage__scroll">
        <div className="ooa-response-card">
          <MessageBubble msg={userMessage} onSuggestion={onSuggestion} />
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
              pendingLabel={loading ? loadingStage : null}
              pendingVizType={loading ? pendingVizType : null}
              toolSteps={loading ? toolSteps : null}
              onSuggestion={onSuggestion}
              onShowMoreSuggestions={onShowMoreSuggestions}
              loadingMoreSuggestions={loadingMoreSuggestions}
              language={language}
              visualizeDragContext={visualizeDragContext}
              onVisualizeDragStart={onVisualizeDragStart}
              onVisualizeDragEnd={onVisualizeDragEnd}
            />
          )}
        </div>
      </div>
    </section>
  );
}
