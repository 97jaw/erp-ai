import { useEffect, useRef } from "react";
import { IconDeepThink, IconMic, IconSend } from "../../components/common/MainIcons";
import { filterLiveSuggestions } from "../../utils/layoutContent";

const MAX_TEXTAREA_HEIGHT = 200;

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
  onStartRecording,
  onStopRecording,
  onSelectSuggestion,
  showSuggestions = true,
  deepThink = false,
  deepThinkEligible = false,
  onToggleDeepThink,
}) {
  const textareaRef = useRef(null);
  const ref = inputRef || textareaRef;
  const suggestions = showSuggestions ? filterLiveSuggestions(input) : [];

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT)}px`;
  }, [input, ref]);

  const handleChange = (event) => {
    const el = event.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT)}px`;
    onInputChange(event);
  };

  const voiceLabel =
    voicePhase === "recording"
      ? "Recording — release to send"
      : voicePhase === "transcribing"
        ? "Transcribing voice"
        : voicePhase === "processing"
          ? "Processing voice request"
          : "Hold to speak";

  return (
    <div
      className={`ooa-chat-input-bar${recording ? " ooa-chat-input-bar--recording" : ""}${
        voicePhase && voicePhase !== "idle" ? ` ooa-chat-input-bar--voice-${voicePhase}` : ""
      }`}
    >
      <div className="ooa-chat-input-bar__panel">
        <div className="ooa-chat-input-bar__leading">
        <button
          type="button"
          className={`ooa-chat-input-bar__mic${recording ? " ooa-chat-input-bar__mic--active" : ""}`}
          aria-label={voiceLabel}
          aria-pressed={recording}
          onPointerDown={(event) => {
            event.preventDefault();
            onStartRecording?.();
          }}
          onPointerUp={(event) => {
            event.preventDefault();
            onStopRecording?.();
          }}
          onPointerLeave={(event) => {
            if (recording) {
              event.preventDefault();
              onStopRecording?.();
            }
          }}
        >
          <IconMic size={18} />
          {recording ? <span className="ooa-chat-input-bar__mic-pulse" aria-hidden="true" /> : null}
        </button>
        </div>
        <textarea
          ref={ref}
          id="chat-input"
          className="ooa-chat-input-bar__textarea"
          rows={1}
          value={input}
          dir={rtlInput ? "rtl" : "ltr"}
          placeholder={
            voicePhase === "recording"
              ? "Listening…"
              : voicePhase === "transcribing"
                ? "Transcribing…"
                : voicePhase === "processing"
                  ? "Processing…"
                  : "Type or speak…"
          }
          disabled={loading || voicePhase === "transcribing" || voicePhase === "processing"}
          onChange={handleChange}
          onKeyDown={onKeyDown}
          aria-label="Chat message"
        />
        <div className="ooa-chat-input-bar__trailing">
          <button
            type="button"
            className={`ooa-chat-input-bar__deepthink${
              deepThink && deepThinkEligible ? " ooa-chat-input-bar__deepthink--active" : ""
            }${!deepThinkEligible ? " ooa-chat-input-bar__deepthink--unavailable" : ""}`}
            disabled={!deepThinkEligible || loading}
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
            disabled={!input.trim() || loading}
            onClick={onSend}
            aria-label="Send message"
          >
            <IconSend size={18} />
          </button>
        </div>
      </div>
      <p className="ooa-chat-input-bar__hint">
        {voicePhase === "recording"
          ? "Release the mic when finished"
          : voicePhase === "transcribing"
            ? "Converting speech to text…"
            : voicePhase === "processing"
              ? "Getting your answer…"
              : "Hold mic to speak · Press any key to type"}
      </p>
      {suggestions.length && input.trim() ? (
        <ul className="ooa-chat-input-bar__suggestions">
          {suggestions.map((item) => (
            <li key={item}>
              <button type="button" onClick={() => onSelectSuggestion?.(item)}>
                {item}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
