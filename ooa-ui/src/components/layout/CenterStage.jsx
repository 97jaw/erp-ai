import MessageBubble from "../chat/MessageBubble";

export default function CenterStage({
  query,
  loading,
  loadingStage,
  pendingVizType,
  toolSteps,
  onSuggestion,
}) {
  if (!query) return null;

  const userMessage = {
    id: `${query.id}-user`,
    role: "user",
    text: query.question,
    visualization: null,
    suggestions: [],
  };

  const botMessage = {
    id: `${query.id}-bot`,
    role: "bot",
    text: query.response?.text || "",
    visualization: query.response?.visualization || null,
    suggestions: query.response?.suggestions || [],
  };

  return (
    <section className="ooa-center-stage" aria-live="polite">
      <div className="ooa-center-stage__scroll">
        <div className="ooa-response-card">
          <MessageBubble msg={userMessage} onSuggestion={onSuggestion} />
          <MessageBubble
            msg={botMessage}
            pendingLabel={loading ? loadingStage : null}
            pendingVizType={loading ? pendingVizType : null}
            toolSteps={loading ? toolSteps : null}
            onSuggestion={onSuggestion}
          />
        </div>
      </div>
    </section>
  );
}
