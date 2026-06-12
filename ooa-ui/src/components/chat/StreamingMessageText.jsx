import { useMemo } from "react";
import { detectTextDirection, humanizeOutput } from "../../utils/chat";

export default function StreamingMessageText({
  text,
  language = "en",
  isStreaming = false,
}) {
  const paragraphs = useMemo(
    () => String(text || "").split(/\n+/).filter((part) => part.trim()),
    [text],
  );

  if (!paragraphs.length && !isStreaming) return null;

  const prefer = language?.startsWith("ar") ? "rtl" : "ltr";

  return (
    <>
      {paragraphs.map((paragraph, index) => {
        const direction = detectTextDirection(paragraph, { prefer });
        return (
          <p
            key={`${index}-${paragraph.slice(0, 12)}`}
            className="ooa-streaming-text__para"
            dir={direction}
            style={{
              textAlign: direction === "rtl" ? "right" : "left",
              margin: index === 0 ? 0 : "0.65em 0 0",
            }}
          >
            {humanizeOutput(paragraph)}
          </p>
        );
      })}
      {isStreaming ? <span className="ooa-bubble__cursor" aria-hidden="true" /> : null}
    </>
  );
}
