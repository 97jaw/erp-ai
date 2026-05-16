import { motion } from "framer-motion";
import { filterLiveSuggestions } from "../../utils/layoutContent";

export default function SpotlightInput({
  input,
  loading,
  recording,
  voicePlaying,
  rtlInput,
  onInputChange,
  onKeyDown,
  onSend,
  onStartRecording,
  onStopRecording,
  onStopVoicePlayback,
  onSelectSuggestion,
}) {
  const suggestions = filterLiveSuggestions(input);

  return (
    <div className={`ooa-spotlight ${recording ? "ooa-spotlight--recording" : ""}`}>
      <div className="ooa-spotlight__panel">
        <button
          type="button"
          className={`ooa-mic-btn ${recording ? "ooa-mic-btn--active" : ""}`}
          onPointerDown={(event) => {
            event.preventDefault();
            onStartRecording();
          }}
          onPointerUp={(event) => {
            event.preventDefault();
            onStopRecording();
          }}
          onPointerLeave={(event) => {
            if (recording) {
              event.preventDefault();
              onStopRecording();
            }
          }}
          onPointerCancel={(event) => {
            event.preventDefault();
            onStopRecording();
          }}
          title="Hold to speak"
        >
          🎤
        </button>
        <textarea
          className="ooa-spotlight__input"
          value={input}
          onChange={onInputChange}
          onKeyDown={onKeyDown}
          placeholder="Type your question or speak..."
          rows={1}
          disabled={loading}
          autoFocus
          style={{
            direction: rtlInput ? "rtl" : "ltr",
            textAlign: rtlInput ? "right" : "left",
          }}
        />
        <div className="ooa-spotlight__actions">
          {voicePlaying ? (
            <button type="button" className="ooa-glass-button" onClick={onStopVoicePlayback}>
              Stop
            </button>
          ) : null}
          <motion.button
            type="button"
            className="ooa-send-btn"
            disabled={!input.trim() || loading}
            onClick={onSend}
            whileHover={input.trim() && !loading ? { rotate: 12, scale: 1.04 } : undefined}
            whileTap={input.trim() && !loading ? { scale: 0.94 } : undefined}
          >
            {loading ? "…" : "↑"}
          </motion.button>
        </div>
      </div>
      {suggestions.length ? (
        <div className="ooa-live-suggestions">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              className="ooa-live-suggestions__item"
              onClick={() => onSelectSuggestion(suggestion)}
            >
              {suggestion}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
