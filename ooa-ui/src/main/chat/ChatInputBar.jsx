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
        {deepThinkEligible ? (
          <button
            type="button"
            className={`ooa-chat-input-bar__deepthink${
              deepThink ? " ooa-chat-input-bar__deepthink--active" : ""
            }`}
            disabled={loading}
            onClick={() => onToggleDeepThink?.()}
            aria-pressed={deepThink}
            aria-label={deepThink ? "Deep Think on — will pull live Odoo data" : "Enable Deep Think"}
            title={
              deepThink
                ? "Deep Think on: pulls actual figures from Odoo"
                : "Deep Think: pull actual figures from Odoo"
            }
          >
            <IconDeepThink size={18} />
          </button>
        ) : null}
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
