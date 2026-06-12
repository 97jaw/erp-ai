import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { streamAuditChat } from "./api";
import { AUDIT_SUGGESTIONS } from "./auditUtils";
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

export default function AuditPanel({ user, embedded = false }) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [narrative, setNarrative] = useState("");
  const [auditData, setAuditData] = useState(null);
  const [sessionId] = useState(() => readAuditSessionId());
  const scrollRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    persistAuditSessionId(sessionId);
  }, [sessionId]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [narrative, auditData, loading]);

  const sendQuery = useCallback(
    async (message) => {
      const trimmed = String(message || "").trim();
      if (!trimmed || loading) return;

      setLoading(true);
      setStatus("Analyzing audit trail...");
      setNarrative("");
      setAuditData(null);

      let streamed = "";
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
            }
            if (event.type === "audit_data" && event.audit_data) {
              setAuditData(event.audit_data);
            }
            if (event.type === "done") {
              if (event.text) setNarrative(event.text);
              if (event.audit_data) setAuditData(event.audit_data);
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
    [loading, sessionId],
  );

  const handleSubmit = (event) => {
    event.preventDefault();
    const value = input;
    setInput("");
    sendQuery(value);
  };

  const handleRecordSelect = ({ model, recordId, name }) => {
    sendQuery(`Show audit trail for ${name || model} (${model}, id ${recordId})`);
  };

  const showEmpty = !loading && !narrative && !auditData;

  return (
    <div className={`ooa-audit-panel${embedded ? " ooa-audit-panel--embedded" : ""}`}>
      <header className="ooa-audit-panel__header">
        <div>
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

      <div className="ooa-audit-panel__body" ref={scrollRef}>
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
