export default function VoiceStatusBanner({ phase }) {
  if (!phase || phase === "idle") return null;

  const copy =
    phase === "recording"
      ? { title: "Listening…", subtitle: "Release to send" }
      : phase === "transcribing"
        ? { title: "Transcribing…", subtitle: "Converting speech to text" }
        : phase === "processing"
          ? { title: "Thinking…", subtitle: "Preparing your answer" }
          : { title: "Working…", subtitle: "" };

  return (
    <div
      className={`ooa-voice-banner ooa-voice-banner--${phase}`}
      role="status"
      aria-live="polite"
      aria-label={copy.title}
    >
      <div className="ooa-voice-banner__orb" aria-hidden="true">
        <span className="ooa-voice-banner__ring" />
        <span className="ooa-voice-banner__ring ooa-voice-banner__ring--delay" />
        <span className="ooa-voice-banner__dot" />
      </div>
      <div className="ooa-voice-banner__text">
        <strong>{copy.title}</strong>
        {copy.subtitle ? <span>{copy.subtitle}</span> : null}
      </div>
      {phase === "recording" ? (
        <div className="ooa-voice-banner__bars" aria-hidden="true">
          {Array.from({ length: 5 }, (_, index) => (
            <span key={index} className="ooa-voice-banner__bar" />
          ))}
        </div>
      ) : (
        <div className="ooa-voice-banner__spinner" aria-hidden="true" />
      )}
    </div>
  );
}
