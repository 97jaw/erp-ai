import { useCallback, useEffect, useRef, useState } from "react";
import { authFetch } from "../config/api";
import AdaptiveUI, { FileReadyList } from "./AdaptiveUI";
import "./reports.css";

const REPORTS_SESSION_KEY = "ooa_reports_session_id";

function readSessionId() {
  try {
    return localStorage.getItem(REPORTS_SESSION_KEY) || crypto.randomUUID();
  } catch {
    return `reports-${Date.now()}`;
  }
}

function persistSessionId(id) {
  try {
    localStorage.setItem(REPORTS_SESSION_KEY, id);
  } catch {
    /* ignore */
  }
}

async function streamReportsChat({ sessionId, message, onEvent }) {
  const res = await authFetch("/reports/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "Request failed");
    throw new Error(text || "Reports request failed");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        const data = JSON.parse(line.slice(6));
        onEvent?.(data);
      } catch {
        /* ignore malformed chunks */
      }
    }
  }
}

// A single chat message row
function Message({ msg, onUserAction }) {
  if (msg.role === "user") {
    return (
      <div className="rpt-msg rpt-msg--user">
        <div className="rpt-msg__bubble">{msg.text}</div>
      </div>
    );
  }

  // Agent: may have text + ui_blocks + files
  return (
    <div className="rpt-msg rpt-msg--agent">
      {msg.text ? <div className="rpt-msg__bubble">{msg.text}</div> : null}
      {(msg.uiBlocks || []).map((block, i) => (
        <AdaptiveUI key={i} block={block} onUserAction={onUserAction || (() => {})} />
      ))}
      {msg.files?.length ? <FileReadyList files={msg.files} /> : null}
    </div>
  );
}

export default function ReportsPanel({ user, embedded = false, onCloseToChat }) {
  const [sessionId] = useState(() => {
    const id = readSessionId();
    persistSessionId(id);
    return id;
  });

  const [messages, setMessages] = useState([]);
  const [pendingBlocks, setPendingBlocks] = useState([]); // ui_blocks accumulated during stream
  const [pendingFiles, setPendingFiles] = useState([]);   // file_ready_list accumulated
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [streamingText, setStreamingText] = useState("");

  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const didGreetRef = useRef(false);

  const scrollToBottom = useCallback(() => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingText, scrollToBottom]);

  const sendMessage = useCallback(
    async (text) => {
      const trimmed = String(text || "").trim();
      if (!trimmed || loading) return;

      // Add user message
      setMessages((prev) => [...prev, { role: "user", text: trimmed }]);
      setLoading(true);
      setStatus("Thinking...");
      setStreamingText("");
      setPendingBlocks([]);
      setPendingFiles([]);

      let streamed = "";
      const localBlocks = [];
      const localFiles = [];

      try {
        await streamReportsChat({
          sessionId,
          message: trimmed,
          onEvent: (event) => {
            if (event.type === "text" && event.chunk) {
              streamed += event.chunk;
              setStreamingText(streamed);
            }
            if (event.type === "status" && event.message) {
              setStatus(event.message);
            }
            if (event.type === "ui_block" && event.block) {
              localBlocks.push(event.block);
              setPendingBlocks([...localBlocks]);
            }
            if (event.type === "file_ready_list" && event.files) {
              localFiles.push(...event.files);
              setPendingFiles([...localFiles]);
            }
            if (event.type === "done") {
              if (event.text) streamed = event.text;
            }
            if (event.type === "error" && event.message) {
              setStatus(event.message);
            }
          },
        });
      } catch (err) {
        streamed = "";
        setStatus(err.message || "Something went wrong");
      } finally {
        // Commit agent turn to messages
        setMessages((prev) => [
          ...prev,
          {
            role: "agent",
            text: streamed,
            uiBlocks: [...localBlocks],
            files: [...localFiles],
          },
        ]);
        setStreamingText("");
        setPendingBlocks([]);
        setPendingFiles([]);
        setLoading(false);
        setStatus("");
      }
    },
    [loading, sessionId],
  );

  // Auto-greet on first render
  useEffect(() => {
    if (!didGreetRef.current) {
      didGreetRef.current = true;
      sendMessage("Hello");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // When user makes a selection from AdaptiveUI
  const handleUiAction = useCallback(
    (selectionText) => {
      sendMessage(selectionText);
    },
    [sendMessage],
  );

  const handleSubmit = (e) => {
    e.preventDefault();
    const val = input;
    setInput("");
    sendMessage(val);
  };

  return (
    <div className="rpt-panel">
      {/* Early-access banner */}
      <div className="rpt-banner" role="note">
        Reports is an early-access feature — still in development. You are welcome to try it!
      </div>

      {/* Header */}
      <header className="rpt-panel__header">
        <div className="rpt-panel__header-text">
          <p style={{ margin: 0, fontSize: 11, opacity: 0.7, textTransform: "uppercase", letterSpacing: 1 }}>
            Generate
          </p>
          <h1>Reports Agent</h1>
          <p>P&amp;L, Trial Balance, and Project Expense exports in PDF or Excel.</p>
        </div>
        {embedded && onCloseToChat ? (
          <button
            type="button"
            className="rpt-panel__close"
            onClick={onCloseToChat}
            aria-label="Back to chat"
            title="Back to chat"
          >
            ×
          </button>
        ) : null}
      </header>

      {/* Message body */}
      <div className="rpt-panel__body" ref={scrollRef}>
        {messages.map((msg, i) => {
          const isLastAgent = msg.role === "agent" &&
            !loading &&
            i === messages.length - 1;
          return (
            <Message
              key={i}
              msg={msg}
              onUserAction={isLastAgent ? handleUiAction : null}
            />
          );
        })}

        {/* Streaming in-progress turn */}
        {loading && (streamingText || pendingBlocks.length || pendingFiles.length) ? (
          <div className="rpt-msg rpt-msg--agent">
            {streamingText ? (
              <div className="rpt-msg__bubble">{streamingText}</div>
            ) : null}
            {pendingBlocks.map((block, i) => (
              <AdaptiveUI key={i} block={block} onUserAction={handleUiAction} />
            ))}
            {pendingFiles.length ? <FileReadyList files={pendingFiles} /> : null}
          </div>
        ) : null}

        {loading && !streamingText && !pendingBlocks.length ? (
          <div className="rpt-panel__status">
            <span className="rpt-spinner" aria-hidden="true" />
            {status || "Working..."}
          </div>
        ) : null}
      </div>

      {/* Composer — also shows after agent messages with UI blocks for typing */}
      <form className="rpt-panel__composer" onSubmit={handleSubmit}>
        <textarea
          ref={inputRef}
          className="rpt-panel__input"
          rows={1}
          placeholder="Type a message or make a selection above..."
          value={input}
          disabled={loading}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
        />
        <button
          type="submit"
          className="rpt-panel__send"
          disabled={loading || !input.trim()}
          aria-label="Send message"
        >
          →
        </button>
      </form>

      {user?.userName ? (
        <footer style={{ padding: "6px 20px", fontSize: 11, color: "var(--ooa-text-muted, #999)", borderTop: "1px solid var(--ooa-border, #dee2e6)" }}>
          Signed in as {user.userName}
        </footer>
      ) : null}
    </div>
  );
}
