import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import AdaptiveUI from "../reports/AdaptiveUI";
import { streamAuditChat } from "./api";
import { AUDIT_SUGGESTIONS, buildSummaryFromAuditData } from "./auditUtils";
import AuditActivityLog from "./AuditActivityLog";
import AuditSummaryBar from "./AuditSummaryBar";
import AuditTimeline from "./AuditTimeline";
import "./styles/audit.css";

const AUDIT_SESSION_KEY = "ooa_audit_session_id";

function readAuditSessionId() {
  try {
    return localStorage.getItem(AUDIT_SESSION_KEY) || crypto.randomUUID();
  } catch {
    return `audit-${Date.now()}`;
  }
}

function persistAuditSessionId(sessionId) {
  try {
    localStorage.setItem(AUDIT_SESSION_KEY, sessionId);
  } catch {
    /* ignore */
  }
}

function viewLabel(auditData, narrative) {
  const summary = buildSummaryFromAuditData(auditData);
  if (summary?.label) return summary.label;
  const preview = String(narrative || "").trim().split(/\n/)[0];
  if (preview) return preview.slice(0, 48);
  return "Previous results";
}

export default function AuditPanel({ user, embedded = false, onCloseToChat }) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [narrative, setNarrative] = useState("");
  const [auditData, setAuditData] = useState(null);
  const [uiBlocks, setUiBlocks] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [viewStack, setViewStack] = useState([]);
  const [sessionId] = useState(() => readAuditSessionId());
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const pinnedToBottomRef = useRef(true);

  useEffect(() => {
    persistAuditSessionId(sessionId);
  }, [sessionId]);

  const scrollToBottomIfPinned = useCallback((behavior = "auto") => {
    const el = scrollRef.current;
    if (!el || !pinnedToBottomRef.current) return;
    el.scrollTo({ top: el.scrollHeight, behavior });
  }, []);

  const handleBodyScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    pinnedToBottomRef.current = distance < 80;
  }, []);

  useEffect(() => {
    scrollToBottomIfPinned("smooth");
  }, [narrative, auditData, scrollToBottomIfPinned]);

  const goBack = useCallback(() => {
    pinnedToBottomRef.current = false;
    setViewStack((prev) => {
      if (!prev.length) return prev;
      const next = [...prev];
      const frame = next.pop();
      setNarrative(frame.narrative || "");
      setAuditData(frame.auditData || null);
      return next;
    });
    window.requestAnimationFrame(() => {
      const el = scrollRef.current;
      if (el) el.scrollTop = 0;
    });
  }, []);

  useEffect(() => {
    if (!viewStack.length) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape" && !loading) {
        event.preventDefault();
        goBack();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [goBack, loading, viewStack.length]);

  const sendQuery = useCallback(
    async (message, options = {}) => {
      const trimmed = String(message || "").trim();
      if (!trimmed || loading) return;

      if (options.pushHistory && (auditData || narrative)) {
        setViewStack((prev) => [
          ...prev,
          {
            narrative,
            auditData,
            label: options.historyLabel || viewLabel(auditData, narrative),
          },
        ]);
      } else if (!options.pushHistory) {
        setViewStack([]);
      }

      pinnedToBottomRef.current = true;
      setLoading(true);
      setStatus("Analyzing audit trail...");
      setNarrative("");
      setAuditData(null);
      setUiBlocks([]);
      setSuggestions([]);
      window.requestAnimationFrame(() => {
        const el = scrollRef.current;
        if (el) el.scrollTop = 0;
      });

      let streamed = "";
      const localBlocks = [];
      try {
        await streamAuditChat({
          sessionId,
          message: trimmed,
          onEvent: (event) => {
            if (event.type === "status" && event.message) {
              setStatus(event.message);
            }
            if (event.type === "text" && event.chunk) {
              streamed += event.chunk;
              setNarrative(streamed);
              setStatus("");
            }
            if (event.type === "ui_block" && event.block) {
              localBlocks.push(event.block);
              setUiBlocks([...localBlocks]);
            }
            if (event.type === "audit_data" && event.audit_data) {
              setAuditData(event.audit_data);
            }
            if (event.type === "done") {
              // Only use done.text as fallback — if text was already streamed,
              // keep the streamed version to avoid a double-text reset effect.
              if (event.text && !streamed) setNarrative(event.text);
              if (event.audit_data) setAuditData(event.audit_data);
              if (event.ui_blocks?.length) {
                setUiBlocks(event.ui_blocks);
              }
              if (event.suggestions?.length) {
                setSuggestions(event.suggestions);
              }
            }
            if (event.type === "error" && event.message) {
              setStatus(event.message);
            }
          },
        });
      } catch (error) {
        setStatus(error.message || "Audit request failed");
      } finally {
        setLoading(false);
        setStatus("");
      }
    },
    [auditData, loading, narrative, sessionId],
  );

  const handleSubmit = (event) => {
    event.preventDefault();
    const value = input;
    setInput("");
    sendQuery(value);
  };

  const handleRecordSelect = ({ model, recordId, name }) => {
    sendQuery(`Show audit trail for ${name || model} (${model}, id ${recordId})`, {
      pushHistory: true,
      historyLabel: name || model,
    });
  };

  const handleUiAction = useCallback(
    (selectionText) => {
      sendQuery(selectionText);
    },
    [sendQuery],
  );

  const backTargetLabel = viewStack.length
    ? viewStack[viewStack.length - 1]?.label
    : null;

  const showEmpty = !loading && !narrative && !auditData;

  return (
    <div className={`ooa-audit-panel${embedded ? " ooa-audit-panel--embedded" : ""}`}>
      <header className="ooa-audit-panel__header">
        {embedded && onCloseToChat ? (
          <button
            type="button"
            className="ooa-audit-panel__close-chat"
            onClick={onCloseToChat}
            aria-label="Back to chat"
            title="Back to chat"
          >
            ×
          </button>
        ) : null}
        <div className="ooa-audit-panel__header-text">
          <p className="ooa-audit-panel__eyebrow">Investigate</p>
          <h1 className="ooa-audit-panel__title">Audit Agent</h1>
          <p className="ooa-audit-panel__subtitle">
            Change history, user activity, and field-level timelines across project records.
          </p>
        </div>
        {!embedded ? (
          <Link to="/" className="ooa-audit-panel__back">
            ← Back to Chat
          </Link>
        ) : null}
      </header>

      <div
        className="ooa-audit-panel__body"
        ref={scrollRef}
        onScroll={handleBodyScroll}
      >
        {showEmpty ? (
          <div className="ooa-audit-panel__empty">
            <div className="ooa-audit-panel__empty-icon" aria-hidden="true">
              ◷
            </div>
            <h2>What would you like to investigate?</h2>
            <p>Ask about changes on a project, agreement, or user activity for a period.</p>
            <div className="ooa-audit-panel__suggestions">
              {AUDIT_SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  className="ooa-audit-suggestion"
                  onClick={() => sendQuery(suggestion)}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {viewStack.length > 0 ? (
          <div className="ooa-audit-panel__nav">
            <button
              type="button"
              className="ooa-audit-panel__nav-back"
              onClick={goBack}
            >
              ← Back to {backTargetLabel || "previous"}
            </button>
            {viewStack.length > 1 ? (
              <span className="ooa-audit-panel__nav-depth">
                {viewStack.length} level{viewStack.length === 1 ? "" : "s"} deep
              </span>
            ) : null}
          </div>
        ) : null}

        {auditData ? (
          <div className="ooa-audit-panel__viz">
            <AuditSummaryBar
              auditData={auditData}
              period={auditData.period}
            />
            {auditData.view === "timeline" ? (
              <AuditTimeline timeline={auditData.timeline || []} />
            ) : null}
            {auditData.view === "activity" ? (
              <AuditActivityLog
                byModel={auditData.by_model || []}
                onRecordSelect={handleRecordSelect}
              />
            ) : null}
          </div>
        ) : null}

        {narrative ? (
          <div className="ooa-audit-panel__narrative">
            <h3 className="ooa-audit-panel__narrative-label">Analysis</h3>
            <div className="ooa-audit-panel__narrative-text">{narrative}</div>
          </div>
        ) : null}

        {uiBlocks.length ? (
          <div className="ooa-audit-panel__ui-blocks">
            {uiBlocks.map((block, index) => (
              <AdaptiveUI
                key={`${block.type}-${index}`}
                block={block}
                onUserAction={handleUiAction}
              />
            ))}
          </div>
        ) : null}

        {suggestions.length ? (
          <div className="ooa-audit-panel__suggestions">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                className="ooa-audit-suggestion"
                onClick={() => sendQuery(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        ) : null}

        {loading ? (
          <div className="ooa-audit-panel__loading" role="status">
            <span className="ooa-audit-panel__spinner" aria-hidden="true" />
            {status || "Loading audit data..."}
          </div>
        ) : null}
      </div>

      <form className="ooa-audit-panel__composer" onSubmit={handleSubmit}>
        <textarea
          ref={inputRef}
          className="ooa-audit-panel__input"
          rows={1}
          placeholder="Ask about changes, timelines, or user activity..."
          value={input}
          disabled={loading}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              handleSubmit(event);
            }
          }}
        />
        <button
          type="submit"
          className="ooa-audit-panel__send"
          disabled={loading || !input.trim()}
          aria-label="Send audit query"
        >
          →
        </button>
      </form>

      {user?.userName ? (
        <footer className="ooa-audit-panel__footer">
          Signed in as {user.userName}
        </footer>
      ) : null}
    </div>
  );
}
