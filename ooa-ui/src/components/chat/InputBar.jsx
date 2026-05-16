import { motion } from "framer-motion";

export default function InputBar({
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
}) {
  return (
    <footer className={`ooa-input-footer ${recording ? "ooa-input-footer--recording" : ""}`}>
      <div className={`ooa-input-wrap ${recording ? "ooa-input-wrap--recording" : ""}`}>
        <textarea
          className="ooa-input"
          value={input}
          onChange={onInputChange}
          onKeyDown={onKeyDown}
          placeholder="Ask anything in English or Arabic... اسأل بالعربية أو الإنجليزية"
          rows={1}
          disabled={loading}
          style={{
            direction: rtlInput ? "rtl" : "ltr",
            textAlign: rtlInput ? "right" : "left",
          }}
        />
        <div className="ooa-input-actions">
          {voicePlaying ? (
            <button type="button" className="ooa-glass-button" onClick={onStopVoicePlayback}>
              Stop
            </button>
          ) : null}
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
      <div className="ooa-input-hint">Press Enter to send · Hold 🎤 to speak · Ask in any language</div>
    </footer>
  );
}
