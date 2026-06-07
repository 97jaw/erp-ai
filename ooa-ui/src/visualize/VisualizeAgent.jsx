import { useCallback, useEffect, useRef, useState } from "react";
import {
  buildVisualizeReport,
  fetchVisualizeLayouts,
  fetchVisualizeThemes,
  resolveOutputUrl,
  startVisualizeSession,
  streamVisualizeChat,
} from "./api";
import AnalysisAccordion from "./cards/AnalysisAccordion";
import CollapsibleSection from "./cards/CollapsibleSection";
import FormatPicker from "./FormatPicker";
import ReportOptionsPanel from "./ReportOptionsPanel";
import {
  buildButtonLabel,
  formatRecommendationDraft,
  normalizeOutputFormat,
} from "./formatUtils";
import { useVisualizeBrain } from "./useVisualizeBrain";

const DEFAULT_THEME = "elegant_gold";
const DEFAULT_LAYOUT = "executive";

function userMessage(text) {
  return {
    id: `user-${Date.now()}`,
    role: "user",
    text,
  };
}

function agentMessage(text, extras = {}) {
  return {
    id: `agent-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    role: "agent",
    text,
    ...extras,
  };
}

export default function VisualizeAgent({
  droppedItems,
  chatSessionId,
  sessionId: externalSessionId,
  onSessionId,
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(externalSessionId || null);
  const [output, setOutput] = useState(null);
  const [error, setError] = useState(null);
  const [toolSteps, setToolSteps] = useState([]);
  const [themes, setThemes] = useState([]);
  const [layouts, setLayouts] = useState([]);
  const [selectedTheme, setSelectedTheme] = useState(DEFAULT_THEME);
  const [selectedLayout, setSelectedLayout] = useState(DEFAULT_LAYOUT);
  const [selectedFormat, setSelectedFormat] = useState("pdf");
  const [includeLogo, setIncludeLogo] = useState(true);
  const [pageNumbers, setPageNumbers] = useState(true);
  const [watermark, setWatermark] = useState("none");
  const scrollRef = useRef(null);
  const itemsKeyRef = useRef("");
  const [serverBrain, setServerBrain] = useState(null);
  const brain = useVisualizeBrain(droppedItems, serverBrain);

  const scrollToBottom = useCallback(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, toolSteps, scrollToBottom]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [themeList, layoutList] = await Promise.all([
          fetchVisualizeThemes(),
          fetchVisualizeLayouts(),
        ]);
        if (cancelled) return;
        setThemes(themeList);
        setLayouts(layoutList);
        if (themeList.length && !themeList.some((t) => t.id === selectedTheme)) {
          setSelectedTheme(themeList[0].id);
        }
        if (layoutList.length && !layoutList.some((l) => l.id === selectedLayout)) {
          setSelectedLayout(layoutList[0].id);
        }
      } catch {
        /* pickers stay hidden if catalog fails */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!brain.recommendation) return;
    if (brain.recommendation.theme) {
      setSelectedTheme(brain.recommendation.theme);
    }
    if (brain.recommendation.layout) {
      const layoutMap = {
        executive_summary: "executive",
        detailed_analytical: "detailed",
        comparative: "comparative",
        standard_report: "executive",
        boardroom: "presentation",
      };
      setSelectedLayout(layoutMap[brain.recommendation.layout] || brain.recommendation.layout);
    }
    setSelectedFormat(normalizeOutputFormat(brain.recommendation.format));
  }, [brain.recommendation]);

  useEffect(() => {
    if (!brain.isReady || !brain.recommendation) return;
    setInput(
      formatRecommendationDraft(brain.recommendation, {
        selectedFormat,
        selectedTheme,
        selectedLayout,
        themes,
        layouts,
        includeLogo,
        pageNumbers,
        watermark,
      }),
    );
  }, [
    brain.isReady,
    brain.recommendation,
    selectedFormat,
    selectedTheme,
    selectedLayout,
    themes,
    layouts,
    includeLogo,
    pageNumbers,
    watermark,
  ]);

  useEffect(() => {
    const key = JSON.stringify(droppedItems.map((item) => item.id));
    if (!droppedItems.length) {
      setSessionId(null);
      setMessages([]);
      setInput("");
      setOutput(null);
      itemsKeyRef.current = "";
      return;
    }
    if (key === itemsKeyRef.current) return;
    itemsKeyRef.current = key;
    setOutput(null);
    setMessages([]);
    setInput("");
    setServerBrain(null);

    let cancelled = false;
    (async () => {
      setError(null);
      setLoading(true);
      try {
        const body = await startVisualizeSession(droppedItems, chatSessionId);
        if (cancelled) return;
        setSessionId(body.session_id);
        onSessionId?.(body.session_id);
        if (body.brain) {
          setServerBrain(body.brain);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [droppedItems, chatSessionId, onSessionId]);

  const buildReportMessage = useCallback((formatOverride) => {
    const rec = brain.recommendation;
    if (!rec) return "Build the report from the dropped data.";

    const fmt = normalizeOutputFormat(formatOverride || selectedFormat || rec.format);
    const themeName = themes.find((t) => t.id === selectedTheme)?.name || selectedTheme;
    const layoutName = layouts.find((l) => l.id === selectedLayout)?.name || selectedLayout;
    const logoPart = includeLogo ? "Include company logo." : "No company logo.";
    const pagesPart = pageNumbers ? "Include page numbers." : "No page numbers.";
    const watermarkPart =
      watermark && watermark !== "none"
        ? `Use "${watermark}" watermark.`
        : "No watermark.";

    return (
      `Build a ${fmt.toUpperCase()} report. ` +
      `Use theme "${selectedTheme}" (${themeName}) ` +
      `and layout "${selectedLayout}" (${layoutName}). ` +
      `${logoPart} ${pagesPart} ${watermarkPart} ` +
      `Include sections: ${(rec.section_labels || []).join("; ")}.`
    );
  }, [
    brain.recommendation,
    selectedFormat,
    selectedTheme,
    selectedLayout,
    themes,
    layouts,
    includeLogo,
    pageNumbers,
    watermark,
  ]);

  const sendMessage = useCallback(async (text) => {
    const trimmed = text.trim();
    if (!trimmed || loading || !sessionId) return;

    setError(null);
    setInput("");
    setLoading(true);
    setToolSteps([]);
    setMessages((prev) => [...prev, userMessage(trimmed)]);

    let streamed = "";

    try {
      await streamVisualizeChat({
        sessionId,
        message: trimmed,
        items: droppedItems,
        onEvent: (data) => {
          if (data.type === "text") {
            streamed += data.chunk || "";
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (last?.role === "agent" && last.streaming) {
                return [
                  ...prev.slice(0, -1),
                  { ...last, text: streamed },
                ];
              }
              return [
                ...prev,
                {
                  id: `agent-stream-${Date.now()}`,
                  role: "agent",
                  text: streamed,
                  streaming: true,
                },
              ];
            });
          }
          if (data.type === "progress") {
            setToolSteps(data.steps || []);
          }
          if (data.type === "done") {
            setMessages((prev) => {
              const withoutStream = prev.filter((m) => !m.streaming);
              const agentText = (data.text || streamed || "").trim();
              if (!agentText) return withoutStream;
              return [
                ...withoutStream,
                agentMessage(agentText, { actions: data.actions || [] }),
              ];
            });
            if (data.output) {
              setOutput(data.output);
            }
          }
          if (data.type === "error") {
            setError(data.message || "Visualize agent error");
          }
        },
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setToolSteps([]);
    }
  }, [droppedItems, loading, sessionId]);

  const handleBuild = async () => {
    if (!brain.recommendation || !sessionId || loading) return;
    brain.setShowAlternatives(false);
    setError(null);
    setLoading(true);
    setToolSteps([{ id: "build", label: "Generating report…", status: "running" }]);
    try {
      const result = await buildVisualizeReport({
        sessionId,
        format: selectedFormat,
        theme: selectedTheme,
        layout: selectedLayout,
        includeLogo,
        pageNumbers,
        watermark,
        title: droppedItems[0]?.question?.slice(0, 120),
      });
      setOutput(result);
      setToolSteps([{ id: "build", label: "Report ready", status: "done" }]);
    } catch (err) {
      setError(err.message || "Build failed");
      setToolSteps([]);
    } finally {
      setLoading(false);
    }
  };

  const handleAlternativeSelect = (alt) => {
    brain.setShowAlternatives(false);
    const fmt = normalizeOutputFormat(alt.format);
    setSelectedFormat(fmt);
    sendMessage(
      buildReportMessage(fmt) + (alt.description ? ` ${alt.description}` : ""),
    );
  };

  const downloadUrl = resolveOutputUrl(output);
  const outputReady = Boolean(output && downloadUrl);
  const canBuild = Boolean(droppedItems.length && brain.isReady && brain.recommendation);
  const recommendedFormat = brain.recommendation?.format || "pdf";
  const showChatPane = messages.length > 0 || toolSteps.length > 0 || loading;

  const buildLabel = outputReady
    ? "View / Download"
    : buildButtonLabel(selectedFormat, recommendedFormat, loading);

  return (
    <section
      className={`ooa-viz-agent${brain.isReady ? " ooa-viz-agent--ready" : ""}${outputReady ? " ooa-viz-agent--has-output" : ""}`}
      aria-label="Visualize agent"
    >
      <div ref={scrollRef} className="ooa-viz-agent__body">
        {droppedItems.length ? (
          <>
            <div className="ooa-viz-agent__analysis-pane">
              <AnalysisAccordion
                brain={brain}
                loading={loading}
                onAlternativeSelect={handleAlternativeSelect}
              />
            </div>

            <ReportOptionsPanel
              themes={themes}
              layouts={layouts}
              selectedTheme={selectedTheme}
              selectedLayout={selectedLayout}
              includeLogo={includeLogo}
              pageNumbers={pageNumbers}
              watermark={watermark}
              onThemeChange={setSelectedTheme}
              onLayoutChange={setSelectedLayout}
              onIncludeLogoChange={setIncludeLogo}
              onPageNumbersChange={setPageNumbers}
              onWatermarkChange={setWatermark}
              disabled={loading}
            />
          </>
        ) : (
          <p className="ooa-viz-agent__placeholder">
            Drop a chat response above to start.
          </p>
        )}

        {showChatPane ? (
          <div className="ooa-viz-agent__chat-pane">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`ooa-viz-agent__msg ooa-viz-agent__msg--${msg.role}`}
              >
                {msg.text ? <p>{msg.text}</p> : null}
              </div>
            ))}

            {toolSteps.length ? (
              <ul className="ooa-viz-agent__progress">
                {toolSteps.map((step) => (
                  <li key={step.id} className={`ooa-viz-agent__progress--${step.status}`}>
                    {step.label}
                  </li>
                ))}
              </ul>
            ) : null}

            {loading && !messages.some((m) => m.streaming) ? (
              <p className="ooa-viz-agent__thinking">Building your report…</p>
            ) : null}
          </div>
        ) : null}
      </div>

      <footer className="ooa-viz-agent__footer">
        {error ? <p className="ooa-viz-agent__error">{error}</p> : null}

        {canBuild && !outputReady ? (
          <CollapsibleSection
            icon="📋"
            title="Format"
            subtitle={normalizeOutputFormat(selectedFormat).toUpperCase()}
            defaultOpen
            className="ooa-viz-agent__format-section"
          >
            <FormatPicker
              value={selectedFormat}
              recommended={recommendedFormat}
              onChange={setSelectedFormat}
              disabled={loading}
            />
          </CollapsibleSection>
        ) : null}

        <div className="ooa-viz-agent__primary-action">
          {outputReady ? (
            <a
              className="viz-btn viz-btn--download ooa-viz-agent__primary-btn"
              href={downloadUrl}
              target="_blank"
              rel="noreferrer"
              download
            >
              View / Download
            </a>
          ) : (
            <button
              type="button"
              className="viz-btn viz-btn--primary ooa-viz-agent__primary-btn"
              disabled={loading || !canBuild}
              onClick={handleBuild}
            >
              {buildLabel} →
            </button>
          )}
        </div>

        <form
          className="ooa-viz-agent__input-row"
          onSubmit={(event) => {
            event.preventDefault();
            sendMessage(input);
          }}
        >
          <textarea
            className="ooa-viz-agent__input ooa-viz-agent__textarea"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Tell Visualize what you want…"
            rows={3}
            disabled={!sessionId || loading || !droppedItems.length}
          />
          <button
            type="submit"
            className="ooa-send-btn"
            disabled={!input.trim() || loading || !sessionId}
            title="Send"
          >
            ↑
          </button>
        </form>
      </footer>
    </section>
  );
}
