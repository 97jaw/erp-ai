import { useEffect, useRef } from "react";
import { IconDeepThink, IconMic, IconSend } from "../../components/common/MainIcons";
import { filterLiveSuggestions } from "../../utils/layoutContent";

const MAX_TEXTAREA_HEIGHT = 200;

const VOICE_INLINE_COPY = {
  recording: "Listening",
  transcribing: "Transcribing",
  processing: "Getting your answer",
};

export default function ChatInputBar({
  input,
  inputRef,
  loading,
  recording,
  voicePhase = "idle",
  rtlInput,
  onInputChange,
  onKeyDown,
  onSend,
  onToggleRecording,
  onSelectSuggestion,
  showSuggestions = true,
  deepThink = false,
  deepThinkEligible = false,
  onToggleDeepThink,
}) {
  const textareaRef = useRef(null);
  const ref = inputRef || textareaRef;
  const suggestions = showSuggestions ? filterLiveSuggestions(input) : [];
  const voiceActive = voicePhase === "recording" || voicePhase === "transcribing" || voicePhase === "processing";
  const micBusy = voicePhase === "transcribing" || voicePhase === "processing";

  useEffect(() => {
    const el = ref.current;
    if (!el || voiceActive) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT)}px`;
  }, [input, ref, voiceActive]);

  const handleChange = (event) => {
    const el = event.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT)}px`;
    onInputChange(event);
  };

  const handleMicClick = () => {
    if (micBusy || loading) return;
    onToggleRecording?.();
  };

  const voiceLabel =
    voicePhase === "recording"
      ? "Listening — tap mic to finish"
      : voicePhase === "transcribing"
        ? "Transcribing voice"
        : voicePhase === "processing"
          ? "Processing voice request"
          : "Tap to speak";

  return (
    <div
      className={`ooa-chat-input-bar${recording ? " ooa-chat-input-bar--recording" : ""}${
        voicePhase && voicePhase !== "idle" ? ` ooa-chat-input-bar--voice-${voicePhase}` : ""
      }`}
    >
      <div className="ooa-chat-input-bar__shell">
        {suggestions.length && input.trim() && !voiceActive ? (
          <ul className="ooa-chat-input-bar__suggestions" role="listbox" aria-label="Suggestions">
            {suggestions.map((item) => (
              <li key={item} role="option">
                <button type="button" onClick={() => onSelectSuggestion?.(item)}>
                  {item}
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        <div className="ooa-chat-input-bar__panel">
          <div className="ooa-chat-input-bar__leading">
            <button
              type="button"
              className={`ooa-chat-input-bar__mic${recording ? " ooa-chat-input-bar__mic--active" : ""}`}
              aria-label={voiceLabel}
              aria-pressed={recording}
              disabled={micBusy || loading}
              onClick={handleMicClick}
            >
              <IconMic size={18} />
              {recording ? <span className="ooa-chat-input-bar__mic-pulse" aria-hidden="true" /> : null}
            </button>
          </div>

          <div className="ooa-chat-input-bar__field">
            {voiceActive ? (
              <div
                className={`ooa-chat-input-bar__voice-inline ooa-chat-input-bar__voice-inline--${voicePhase}`}
                role="status"
                aria-live="polite"
                aria-label={`${VOICE_INLINE_COPY[voicePhase]}…`}
              >
                <span className="ooa-chat-input-bar__voice-label">{VOICE_INLINE_COPY[voicePhase]}…</span>
                {voicePhase === "recording" ? (
                  <span className="ooa-chat-input-bar__voice-bars" aria-hidden="true">
                    {Array.from({ length: 4 }, (_, index) => (
                      <span key={index} className="ooa-chat-input-bar__voice-bar" />
                    ))}
                  </span>
                ) : (
                  <span className="ooa-chat-input-bar__voice-spinner" aria-hidden="true" />
                )}
                <span className="ooa-chat-input-bar__voice-cursor" aria-hidden="true" />
              </div>
            ) : null}
            <textarea
              ref={ref}
              id="chat-input"
              className={`ooa-chat-input-bar__textarea${
                voiceActive ? " ooa-chat-input-bar__textarea--hidden" : ""
              }`}
              rows={1}
              value={input}
              dir={rtlInput ? "rtl" : "ltr"}
              placeholder="Type or speak…"
              disabled={loading || voiceActive}
              onChange={handleChange}
              onKeyDown={onKeyDown}
              aria-label="Chat message"
              aria-hidden={voiceActive}
            />
          </div>

          <div className="ooa-chat-input-bar__trailing">
            <button
              type="button"
              className={`ooa-chat-input-bar__deepthink${
                deepThink && deepThinkEligible ? " ooa-chat-input-bar__deepthink--active" : ""
              }${!deepThinkEligible ? " ooa-chat-input-bar__deepthink--unavailable" : ""}`}
              disabled={!deepThinkEligible || loading || voiceActive}
              onClick={() => onToggleDeepThink?.()}
              aria-pressed={deepThink && deepThinkEligible}
              aria-label={
                deepThinkEligible
                  ? deepThink
                    ? "Deep think on — pulls live Odoo data"
                    : "Deep think off — tap to enable live Odoo data"
                  : "Deep think unavailable for this query"
              }
              title={
                deepThinkEligible
                  ? deepThink
                    ? "Deep think on: live figures from Odoo"
                    : "Deep think off: tap to pull live Odoo data"
                  : "Deep think activates for financial and Odoo data queries"
              }
            >
              <IconDeepThink size={16} />
              <span className="ooa-chat-input-bar__deepthink-label">Deep think</span>
            </button>
            <button
              type="button"
              className="ooa-chat-input-bar__send"
              disabled={!input.trim() || loading || voiceActive}
              onClick={onSend}
              aria-label="Send message"
            >
              <IconSend size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
