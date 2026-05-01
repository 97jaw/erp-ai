import { useState, useRef, useEffect, useCallback } from "react";

const API_BASE = "http://localhost:8000";

// ─── Helpers ────────────────────────────────────────────────────────────────

const isArabic = (text = "") => /[\u0600-\u06FF]/.test(text);
const sessionId = () => Math.random().toString(36).slice(2);

// Persist session across refreshes
const SESSION_ID = (() => {
  let id = localStorage.getItem("ooa_session_id");
  if (!id) {
    id = sessionId();
    localStorage.setItem("ooa_session_id", id);
  }
  return id;
})();

// ─── Visual Components ───────────────────────────────────────────────────────

function KPICard({ data }) {
  if (!data) return null;
  const { label, value, unit, data: d } = data;
  const isNeg = value < 0;
  return (
    <div style={styles.kpiCard}>
      <div style={styles.kpiLabel}>{label}</div>
      <div style={{ ...styles.kpiValue, color: isNeg ? "#ff6b6b" : "#4ecdc4" }}>
        {unit} {Math.abs(value).toLocaleString("en-AE", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
      </div>
      {d && (
        <div style={styles.kpiDetails}>
          {Object.entries(d).slice(0, 4).map(([k, v]) =>
            typeof v === "number" ? (
              <div key={k} style={styles.kpiDetailRow}>
                <span style={styles.kpiDetailKey}>{k.replace(/_/g, " ")}</span>
                <span style={styles.kpiDetailVal}>
                  {typeof v === "number" ? v.toLocaleString("en-AE", { minimumFractionDigits: 0, maximumFractionDigits: 2 }) : v}
                </span>
              </div>
            ) : null
          )}
        </div>
      )}
    </div>
  );
}

function DataTable({ data }) {
  if (!data?.data?.rows?.length) return null;
  const { headers, rows } = data.data;
  return (
    <div style={styles.tableWrap}>
      <div style={styles.tableLabel}>{data.label}</div>
      <div style={styles.tableScroll}>
        <table style={styles.table}>
          <thead>
            <tr>
              {(headers || Object.keys(rows[0] || {})).map((h, i) => (
                <th key={i} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 10).map((row, i) => (
              <tr key={i} style={{ background: i % 2 === 0 ? "rgba(255,255,255,0.02)" : "transparent" }}>
                {(Array.isArray(row) ? row : Object.values(row)).map((cell, j) => (
                  <td key={j} style={styles.td}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FinancialReport({ data }) {
  if (!data) return null;
  const { kpis, label, date_from, date_to } = data;
  if (!kpis) return null;
  return (
    <div style={styles.reportCard}>
      <div style={styles.reportHeader}>
        <span style={styles.reportTitle}>{label}</span>
        <span style={styles.reportDate}>{date_from} → {date_to}</span>
      </div>
      <div style={styles.reportKpis}>
        {[
          { label: "Income", value: kpis.total_income, color: "#4ecdc4" },
          { label: "Expenses", value: kpis.total_expense, color: "#ff6b6b" },
          { label: "Net Profit", value: kpis.net_profit, color: kpis.net_profit >= 0 ? "#4ecdc4" : "#ff6b6b" },
          { label: "Margin", value: kpis.margin, unit: "%", color: kpis.margin >= 0 ? "#4ecdc4" : "#ff6b6b" },
        ].map((item) => (
          <div key={item.label} style={styles.reportKpiItem}>
            <div style={styles.reportKpiLabel}>{item.label}</div>
            <div style={{ ...styles.reportKpiValue, color: item.color }}>
              {item.unit === "%" ? `${item.value?.toFixed(2)}%` : `AED ${Math.abs(item.value || 0).toLocaleString("en-AE", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`}
              {item.value < 0 && item.unit !== "%" && <span style={{ fontSize: 11, marginLeft: 4, opacity: 0.7 }}>(Loss)</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Visualization({ viz }) {
  if (!viz) return null;
  const { visual_type } = viz;
  if (visual_type === "KPI_CARD") return <KPICard data={viz} />;
  if (visual_type === "DATA_TABLE") return <DataTable data={viz} />;
  if (visual_type === "FINANCIAL_REPORT") return <FinancialReport data={viz} />;
  return null;
}

function Suggestions({ items, onSelect }) {
  if (!items?.length) return null;
  return (
    <div style={styles.suggestions}>
      {items.map((s, i) => (
        <button key={i} style={styles.suggBtn} onClick={() => onSelect(s)}>
          {s}
        </button>
      ))}
    </div>
  );
}

function Message({ msg }) {
  const isUser = msg.role === "user";
  const rtl = isArabic(msg.text);
  return (
    <div style={{ ...styles.msgWrap, justifyContent: isUser ? "flex-end" : "flex-start" }}>
      {!isUser && (
        <div style={styles.avatar}>
          <span>🤖</span>
        </div>
      )}
      <div style={{ maxWidth: "75%" }}>
        <div
          style={{
            ...styles.bubble,
            ...(isUser ? styles.bubbleUser : styles.bubbleBot),
            direction: rtl ? "rtl" : "ltr",
            textAlign: rtl ? "right" : "left",
          }}
        >
          {msg.text}
        </div>
        {msg.visualization && <Visualization viz={msg.visualization} />}
        {msg.suggestions && (
          <Suggestions items={msg.suggestions} onSelect={msg.onSuggestion} />
        )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div style={{ ...styles.msgWrap, justifyContent: "flex-start" }}>
      <div style={styles.avatar}><span>🤖</span></div>
      <div style={styles.typing}>
        <span style={{ ...styles.dot, animationDelay: "0s" }} />
        <span style={{ ...styles.dot, animationDelay: "0.2s" }} />
        <span style={{ ...styles.dot, animationDelay: "0.4s" }} />
      </div>
    </div>
  );
}

// ─── Main App ────────────────────────────────────────────────────────────────

export default function App() {
  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem("ooa_messages");
      if (saved) {
        const parsed = JSON.parse(saved);
        // Re-attach suggestion handlers
        return parsed.map(msg => ({
          ...msg,
          onSuggestion: null,
        }));
      }
    } catch (e) {}
    return [{
      id: "welcome",
      role: "bot",
      text: "مرحباً! أنا مساعدك الذكي لنظام أودو. يمكنني مساعدتك في التقارير المالية، تكاليف المشاريع، والبحث في قاعدة البيانات.\n\nHello! I'm your Odoo AI assistant. Ask me anything about financials, projects, or your data.",
      visualization: null,
      suggestions: [
        "Profit and loss this month",
        "Total cost for a project",
        "Show active projects",
        "الأرباح والخسائر لهذا الشهر",
      ],
    }];
  });
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);
  const mediaRef = useRef(null);
  const chunksRef = useRef([]);
  // Save messages to localStorage

  useEffect(() => {
    try {
      // Don't save onSuggestion functions — not serializable
      const toSave = messages.map(({ onSuggestion, ...rest }) => rest);
      localStorage.setItem("ooa_messages", JSON.stringify(toSave));
    } catch (e) {}
  }, [messages]);
  // Re-wire suggestion handlers after localStorage load
  useEffect(() => {
    setMessages(prev => prev.map(msg => ({
      ...msg,
      onSuggestion: msg.role === "bot" ? (s) => sendMessage(s) : undefined,
    })));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);
  
  const sendMessage = useCallback(async (text) => {
  if (!text.trim() || loading) return;
  setError(null);
  setInput("");

  const userMsg = { id: Date.now(), role: "user", text };
  setMessages((prev) => [...prev, userMsg]);
  setLoading(true);

  // Add empty bot message that we will fill progressively
  const botId = Date.now() + 1;
  setMessages((prev) => [
    ...prev,
    { id: botId, role: "bot", text: "", visualization: null, suggestions: [] },
  ]);

  try {
    const res = await fetch(`${API_BASE}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: SESSION_ID }),
    });

    if (!res.ok) throw new Error(`Server error: ${res.status}`);

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let   buffer  = "";

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

          if (data.type === "text") {
            // Hide tool fetching indicator from text — shown separately
            const chunk = data.chunk;
            setMessages((prev) => prev.map((msg) =>
              msg.id === botId
                ? { ...msg, text: msg.text + chunk }
                : msg
            ));
          } else if (data.type === "tool") {
            // Show tool being called
            setMessages((prev) => prev.map((msg) =>
              msg.id === botId
                ? { ...msg, text: msg.text + `\n_Fetching ${data.name.replace(/_/g, " ")}..._\n` }
                : msg
            ));
          } else if (data.type === "done") {
              setMessages((prev) => prev.map((msg) => {
                if (msg.id !== botId) return msg;
                // Clean visualization block from displayed text
                let cleanText = msg.text;
                if (cleanText.includes("<visualization>")) {
                  cleanText = cleanText.substring(0, cleanText.indexOf("<visualization>")).trim();
                }
                // Clean tool fetching messages
                cleanText = cleanText.replace(/\n_Fetching [^_]+\.\.\._\n/g, "").replace(/Now let me try[^.]+\./g, "").replace(/Let me try[^.]+\./g, "").replace(/Let me get[^.]+\:/g, "").trim();
                return {
                  ...msg,
                  text         : cleanText,
                  visualization: data.visualization,
                  suggestions  : data.suggestions,
                  onSuggestion : (s) => sendMessage(s),
                };
              }));
            }
        } catch (e) {}
      }
    }
  } catch (err) {
    setError(err.message);
    setMessages((prev) => prev.map((msg) =>
      msg.id === botId
        ? { ...msg, text: "Sorry, I encountered an error. Please try again." }
        : msg
    ));
  } finally {
    setLoading(false);
  }
}, [loading]);

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRef.current = new MediaRecorder(stream);
      chunksRef.current = [];
      mediaRef.current.ondataavailable = (e) => chunksRef.current.push(e.data);
      mediaRef.current.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        stream.getTracks().forEach((t) => t.stop());
        await sendVoice(blob);
      };
      mediaRef.current.start();
      setRecording(true);
    } catch (err) {
      setError("Microphone access denied");
    }
  };

  const stopRecording = () => {
    if (mediaRef.current?.state === "recording") {
      mediaRef.current.stop();
      setRecording(false);
    }
  };

  const sendVoice = async (blob) => {
    setLoading(true);
    setError(null);
    const form = new FormData();
    form.append("audio", blob, "recording.webm");

    try {
      const res = await fetch(`${API_BASE}/voice`, { method: "POST", body: form });
      if (!res.ok) throw new Error(`Voice error: ${res.status}`);

      const transcript = res.headers.get("X-Transcript") || "Voice message";
      const userMsg = { id: Date.now(), role: "user", text: `🎤 ${transcript}` };
      setMessages((prev) => [...prev, userMsg]);

      // Play audio response
      const audioBlob = await res.blob();
      const url = URL.createObjectURL(audioBlob);
      const audio = new Audio(url);
      audio.play();

      // Show text response
      const responseText = res.headers.get("X-Response") || "Processing...";
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "bot",
          text: responseText + "\n\n(Audio response is playing)",
          visualization: null,
          suggestions: [],
          onSuggestion: (s) => sendMessage(s),
        },
      ]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const rtlInput = isArabic(input);

  return (
    <div style={styles.app}>
      {/* Animated background */}
      <div style={styles.bgGlow1} />
      <div style={styles.bgGlow2} />

      {/* Header */}
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <div style={styles.logo}>
            <span style={styles.logoIcon}>◈</span>
            <div>
              <div style={styles.logoTitle}>Odoo Omni-Agent</div>
              <div style={styles.logoSub}>Elrace ERP Intelligence</div>
            </div>
          </div>
        </div>
        <div style={styles.headerRight}>
          <button
            onClick={() => {
              localStorage.removeItem("ooa_messages");
              localStorage.removeItem("ooa_session_id");
              window.location.reload();
            }}
            style={styles.clearBtn}
            title="Clear conversation"
          >
            ↺ Clear
          </button>
          <div style={styles.statusDot} />
          <span style={styles.statusText}>Live</span>
        </div>
      </header>

      {/* Chat area */}
      <main style={styles.main}>
        <div style={styles.messages}>
          {messages.map((msg) => (
            <Message key={msg.id} msg={msg} />
          ))}
          {loading && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>
      </main>

      {/* Error */}
      {error && (
        <div style={styles.error}>
          ⚠ {error}
          <button onClick={() => setError(null)} style={styles.errClose}>×</button>
        </div>
      )}

      {/* Input area */}
      <footer style={styles.footer}>
        <div style={styles.inputWrap}>
          <textarea
            style={{
              ...styles.input,
              direction: rtlInput ? "rtl" : "ltr",
              textAlign: rtlInput ? "right" : "left",
            }}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask anything in English or Arabic... اسأل بالعربية أو الإنجليزية"
            rows={1}
            disabled={loading}
          />
          <div style={styles.inputActions}>
            <button
              style={{
                ...styles.micBtn,
                background: recording ? "#ff6b6b" : "rgba(255,255,255,0.08)",
                animation: recording ? "pulse 1s infinite" : "none",
              }}
              onMouseDown={startRecording}
              onMouseUp={stopRecording}
              onTouchStart={startRecording}
              onTouchEnd={stopRecording}
              title="Hold to speak"
            >
              🎤
            </button>
            <button
              style={{
                ...styles.sendBtn,
                opacity: input.trim() && !loading ? 1 : 0.4,
              }}
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || loading}
            >
              {loading ? "…" : "↑"}
            </button>
          </div>
        </div>
        <div style={styles.hint}>
          Press Enter to send · Hold 🎤 to speak · Ask in any language
        </div>
      </footer>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600&family=Noto+Naskh+Arabic:wght@400;500;600&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0a0f1e; color: #e8eaf6; font-family: 'Sora', 'Noto Naskh Arabic', sans-serif; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }
        @keyframes pulse { 0%,100% { transform: scale(1); } 50% { transform: scale(1.05); } }
        @keyframes bounce { 0%,80%,100% { transform: translateY(0); } 40% { transform: translateY(-6px); } }
        @keyframes fadeUp { from { opacity:0; transform: translateY(12px); } to { opacity:1; transform: translateY(0); } }
      `}</style>
    </div>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────

const styles = {
  app: {
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    background: "#080d1a",
    position: "relative",
    overflow: "hidden",
  },
  bgGlow1: {
    position: "absolute",
    top: -200,
    left: -200,
    width: 600,
    height: 600,
    borderRadius: "50%",
    background: "radial-gradient(circle, rgba(180,140,60,0.06) 0%, transparent 70%)",
    pointerEvents: "none",
  },
  bgGlow2: {
    position: "absolute",
    bottom: -100,
    right: -100,
    width: 400,
    height: 400,
    borderRadius: "50%",
    background: "radial-gradient(circle, rgba(78,205,196,0.04) 0%, transparent 70%)",
    pointerEvents: "none",
  },
  clearBtn: {
    background: "rgba(255,255,255,0.06)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 8,
    color: "rgba(255,255,255,0.4)",
    fontSize: 11,
    padding: "5px 10px",
    cursor: "pointer",
    letterSpacing: "0.04em",
    fontFamily: "inherit",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "16px 24px",
    borderBottom: "1px solid rgba(255,255,255,0.06)",
    background: "rgba(255,255,255,0.02)",
    backdropFilter: "blur(12px)",
    zIndex: 10,
    flexShrink: 0,
  },
  headerLeft: { display: "flex", alignItems: "center" },
  logo: { display: "flex", alignItems: "center", gap: 12 },
  logoIcon: {
    fontSize: 28,
    color: "#c9a84c",
    lineHeight: 1,
    textShadow: "0 0 20px rgba(201,168,76,0.4)",
  },
  logoTitle: {
    fontSize: 16,
    fontWeight: 600,
    color: "#e8eaf6",
    letterSpacing: "0.02em",
  },
  logoSub: {
    fontSize: 11,
    color: "rgba(255,255,255,0.35)",
    letterSpacing: "0.08em",
    textTransform: "uppercase",
  },
  headerRight: { display: "flex", alignItems: "center", gap: 8 },
  statusDot: {
    width: 7,
    height: 7,
    borderRadius: "50%",
    background: "#4ecdc4",
    boxShadow: "0 0 8px #4ecdc4",
  },
  statusText: { fontSize: 12, color: "rgba(255,255,255,0.4)", letterSpacing: "0.06em" },
  main: { flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" },
  messages: {
    flex: 1,
    overflowY: "auto",
    padding: "24px 20px",
    display: "flex",
    flexDirection: "column",
    gap: 20,
    maxWidth: 900,
    width: "100%",
    margin: "0 auto",
  },
  msgWrap: {
    display: "flex",
    gap: 12,
    animation: "fadeUp 0.3s ease",
  },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: "50%",
    background: "linear-gradient(135deg, #1a2744, #0d1b35)",
    border: "1px solid rgba(201,168,76,0.3)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 16,
    flexShrink: 0,
  },
  bubble: {
    padding: "12px 16px",
    borderRadius: 16,
    fontSize: 14,
    lineHeight: 1.7,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  },
  bubbleUser: {
    background: "linear-gradient(135deg, #c9a84c, #a8873d)",
    color: "#0a0f1e",
    borderBottomRightRadius: 4,
    fontWeight: 500,
  },
  bubbleBot: {
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.08)",
    color: "#e8eaf6",
    borderBottomLeftRadius: 4,
  },
  typing: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "14px 18px",
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 16,
    borderBottomLeftRadius: 4,
  },
  dot: {
    display: "inline-block",
    width: 7,
    height: 7,
    borderRadius: "50%",
    background: "#c9a84c",
    animation: "bounce 1.2s infinite",
  },
  // KPI Card
  kpiCard: {
    marginTop: 10,
    padding: 16,
    background: "linear-gradient(135deg, rgba(201,168,76,0.08), rgba(201,168,76,0.03))",
    border: "1px solid rgba(201,168,76,0.2)",
    borderRadius: 12,
  },
  kpiLabel: { fontSize: 11, color: "rgba(255,255,255,0.4)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 6 },
  kpiValue: { fontSize: 28, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 12 },
  kpiDetails: { display: "flex", flexDirection: "column", gap: 4 },
  kpiDetailRow: { display: "flex", justifyContent: "space-between", fontSize: 12, color: "rgba(255,255,255,0.5)" },
  kpiDetailKey: { textTransform: "capitalize" },
  kpiDetailVal: { color: "rgba(255,255,255,0.7)", fontWeight: 500 },
  // Financial Report
  reportCard: {
    marginTop: 10,
    padding: 16,
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 12,
  },
  reportHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 14,
    paddingBottom: 10,
    borderBottom: "1px solid rgba(255,255,255,0.06)",
  },
  reportTitle: { fontSize: 13, fontWeight: 600, color: "#c9a84c" },
  reportDate: { fontSize: 11, color: "rgba(255,255,255,0.3)" },
  reportKpis: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 },
  reportKpiItem: {
    padding: "10px 12px",
    background: "rgba(255,255,255,0.03)",
    borderRadius: 8,
    border: "1px solid rgba(255,255,255,0.06)",
  },
  reportKpiLabel: { fontSize: 10, color: "rgba(255,255,255,0.35)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 },
  reportKpiValue: { fontSize: 16, fontWeight: 600 },
  // Table
  tableWrap: { marginTop: 10 },
  tableLabel: { fontSize: 12, color: "#c9a84c", marginBottom: 8, fontWeight: 500 },
  tableScroll: { overflowX: "auto", borderRadius: 10, border: "1px solid rgba(255,255,255,0.08)" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 12 },
  th: {
    padding: "8px 12px",
    background: "rgba(201,168,76,0.1)",
    color: "#c9a84c",
    fontWeight: 600,
    textAlign: "left",
    whiteSpace: "nowrap",
    letterSpacing: "0.04em",
    fontSize: 11,
  },
  td: { padding: "7px 12px", color: "rgba(255,255,255,0.7)", borderTop: "1px solid rgba(255,255,255,0.04)" },
  // Suggestions
  suggestions: { display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 },
  suggBtn: {
    padding: "6px 12px",
    fontSize: 12,
    background: "rgba(201,168,76,0.08)",
    border: "1px solid rgba(201,168,76,0.25)",
    borderRadius: 20,
    color: "#c9a84c",
    cursor: "pointer",
    transition: "all 0.2s",
    fontFamily: "inherit",
  },
  // Error
  error: {
    margin: "0 20px",
    padding: "10px 16px",
    background: "rgba(255,107,107,0.1)",
    border: "1px solid rgba(255,107,107,0.3)",
    borderRadius: 8,
    fontSize: 13,
    color: "#ff6b6b",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  errClose: {
    background: "none",
    border: "none",
    color: "#ff6b6b",
    fontSize: 18,
    cursor: "pointer",
    lineHeight: 1,
  },
  // Footer
  footer: {
    padding: "16px 20px",
    borderTop: "1px solid rgba(255,255,255,0.06)",
    background: "rgba(255,255,255,0.02)",
    backdropFilter: "blur(12px)",
    flexShrink: 0,
  },
  inputWrap: {
    display: "flex",
    gap: 10,
    alignItems: "flex-end",
    maxWidth: 900,
    margin: "0 auto",
    background: "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 16,
    padding: "8px 8px 8px 16px",
  },
  input: {
    flex: 1,
    background: "transparent",
    border: "none",
    outline: "none",
    color: "#e8eaf6",
    fontSize: 14,
    lineHeight: 1.6,
    resize: "none",
    fontFamily: "inherit",
    maxHeight: 120,
    overflowY: "auto",
    paddingTop: 4,
  },
  inputActions: { display: "flex", gap: 6, alignItems: "center" },
  micBtn: {
    width: 38,
    height: 38,
    borderRadius: "50%",
    border: "none",
    cursor: "pointer",
    fontSize: 16,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    transition: "all 0.2s",
    userSelect: "none",
  },
  sendBtn: {
    width: 38,
    height: 38,
    borderRadius: "50%",
    background: "linear-gradient(135deg, #c9a84c, #a8873d)",
    border: "none",
    color: "#0a0f1e",
    fontSize: 18,
    fontWeight: 700,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    transition: "all 0.2s",
  },
  hint: {
    textAlign: "center",
    fontSize: 11,
    color: "rgba(255,255,255,0.2)",
    marginTop: 8,
    letterSpacing: "0.04em",
  },
};