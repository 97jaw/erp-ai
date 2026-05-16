import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AnimatedBackground from "../background/AnimatedBackground";
import { sound } from "../common/SoundManager";
import { useSoundSettings } from "../../hooks/useSoundSettings";
import {
  API_BASE,
  decodeHeader,
  getRecordingMimeType,
  getStoredSessionId,
  hasRenderableVisualization,
  isArabic,
  normalizeVisualization,
  parseApiError,
  recordingExtension,
  stripVisualization,
} from "../../utils/chat";
import CenterStage from "../layout/CenterStage";
import FloatingChrome from "./FloatingChrome";
import LeftSidebar from "../layout/LeftSidebar";
import NewQuestionButton from "../layout/NewQuestionButton";
import RightSidebar from "../layout/RightSidebar";
import SpotlightInput from "../layout/SpotlightInput";
import WelcomeScreen from "../layout/WelcomeScreen";

const QUERIES_STORAGE_KEY = "ooa_queries";

function loadStoredQueries() {
  try {
    const saved = localStorage.getItem(QUERIES_STORAGE_KEY);
    if (!saved) return [];
    const parsed = JSON.parse(saved);
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    return [];
  }
}

export default function ChatScreen({ sessionId: authSessionId, user, onLogout }) {
  const sessionId = authSessionId || getStoredSessionId();
  const { enabled: soundEnabled, volume, toggleEnabled: toggleSound, updateVolume } = useSoundSettings();
  const [queries, setQueries] = useState(loadStoredQueries);
  const [activeQueryId, setActiveQueryId] = useState(() => loadStoredQueries()[0]?.id || null);
  const [previewQueryId, setPreviewQueryId] = useState(null);
  const [spotlightOpen, setSpotlightOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState(null);
  const [loadingStage, setLoadingStage] = useState(null);
  const [toolSteps, setToolSteps] = useState([]);
  const [pendingVizType, setPendingVizType] = useState(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [voicePlaying, setVoicePlaying] = useState(false);
  const mediaRef = useRef(null);
  const audioRef = useRef(null);
  const chunksRef = useRef([]);
  const recordingMimeRef = useRef("");
  const emptyInputTimerRef = useRef(null);
  const previewTimerRef = useRef(null);

  const activeQuery = useMemo(
    () => queries.find((query) => query.id === activeQueryId) || null,
    [queries, activeQueryId],
  );

  const layoutMode = useMemo(() => {
    if (loading && activeQueryId) return "generating";
    if (spotlightOpen) return "typing";
    if (queries.length > 0) return "viewing";
    return "welcome";
  }, [loading, spotlightOpen, queries.length, activeQueryId]);

  const isPrintableKey = useCallback((event) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return false;
    if (event.key.length !== 1) return false;
    const tag = document.activeElement?.tagName;
    if (tag === "TEXTAREA" || tag === "INPUT") return false;
    return true;
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(QUERIES_STORAGE_KEY, JSON.stringify(queries));
    } catch (error) {}
  }, [queries]);

  useEffect(() => {
    if ((layoutMode === "viewing" || layoutMode === "generating") && queries.length > 0) {
      setHistoryOpen(true);
    }
    if (layoutMode === "welcome") {
      setHistoryOpen(false);
    }
  }, [layoutMode, queries.length]);

  useEffect(() => {
    if (!queries.length) return undefined;

    const onMove = (event) => {
      if (event.clientX >= window.innerWidth - 72) {
        setHistoryOpen(true);
      }
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, [queries.length]);

  const shellClassName = [
    "ooa-app-shell",
    "ooa-layout",
    `ooa-layout--${layoutMode}`,
    historyOpen && queries.length ? "ooa-layout--history-open" : "",
  ].filter(Boolean).join(" ");

  const openSpotlight = useCallback((seed = "") => {
    setSpotlightOpen(true);
    if (seed) setInput(seed);
  }, []);

  const closeSpotlight = useCallback(() => {
    setSpotlightOpen(false);
    setInput("");
  }, []);

  const updateQuery = useCallback((queryId, patch) => {
    setQueries((prev) => prev.map((query) => (
      query.id === queryId ? { ...query, ...patch } : query
    )));
  }, []);

  const sendMessage = useCallback(async (text) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    setError(null);
    setInput("");
    setSpotlightOpen(false);
    sound.play("message-send", { volume: 0.35 });

    const queryId = Date.now();
    const createdAt = Date.now();
    const nextQuery = {
      id: queryId,
      question: trimmed,
      createdAt,
      status: "generating",
      vizType: null,
      response: {
        text: "",
        visualization: null,
        suggestions: [],
      },
    };

    setQueries((prev) => [nextQuery, ...prev]);
    setActiveQueryId(queryId);
    setLoading(true);
    setLoadingStage("Preparing your answer...");
    setPendingVizType(null);
    setToolSteps([]);

    try {
      const res = await fetch(`${API_BASE}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed, session_id: sessionId }),
      });

      if (!res.ok) throw new Error(await parseApiError(res, `Server error: ${res.status}`));

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let streamedText = "";

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
              setLoadingStage(null);
              streamedText += data.chunk;
              updateQuery(queryId, {
                response: {
                  text: stripVisualization(streamedText),
                  visualization: null,
                  suggestions: [],
                },
              });
            } else if (data.type === "viz_hint") {
              if (data.visual_type && data.visual_type !== "NONE") {
                setPendingVizType(data.visual_type);
                updateQuery(queryId, { vizType: data.visual_type });
              }
            } else if (data.type === "progress") {
              setToolSteps(data.steps || []);
            } else if (data.type === "status") {
              setLoadingStage(data.message);
            } else if (data.type === "done") {
              sound.play("message-receive", { volume: 0.3 });
              const visualization = hasRenderableVisualization(data.visualization)
                ? normalizeVisualization(data.visualization)
                : null;
              const serverText = typeof data.text === "string"
                ? stripVisualization(data.text)
                : stripVisualization(streamedText);
              const finalText = serverText || stripVisualization(streamedText);
              updateQuery(queryId, {
                status: "complete",
                vizType: visualization?.visual_type || null,
                response: {
                  text: finalText,
                  visualization,
                  suggestions: data.suggestions || [],
                },
              });
            }
          } catch (error) {}
        }
      }
    } catch (err) {
      setError(err.message);
      updateQuery(queryId, {
        status: "error",
        response: {
          text: "Sorry, I encountered an error. Please try again.",
          visualization: null,
          suggestions: [],
        },
      });
    } finally {
      setLoading(false);
      setLoadingStage(null);
      setPendingVizType(null);
      setToolSteps([]);
    }
  }, [loading, sessionId, updateQuery]);

  const handleInputChange = (event) => {
    const value = event.target.value;
    setInput(value);
    if (emptyInputTimerRef.current) {
      window.clearTimeout(emptyInputTimerRef.current);
    }
    if (!value.trim() && queries.length === 0) {
      emptyInputTimerRef.current = window.setTimeout(() => {
        closeSpotlight();
      }, 200);
    }
  };

  const handleInputKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage(input);
    }
    if (event.key === "Escape") {
      event.preventDefault();
      closeSpotlight();
    }
  };

  const handleCloseTab = useCallback((queryId) => {
    setQueries((prev) => {
      const remaining = prev.filter((query) => query.id !== queryId);
      setActiveQueryId((active) => (active === queryId ? remaining[0]?.id || null : active));
      return remaining;
    });
    setPreviewQueryId(null);
  }, []);

  useEffect(() => {
    const onKeyDown = (event) => {
      const isMeta = event.metaKey || event.ctrlKey;
      if ((layoutMode === "welcome" || layoutMode === "viewing") && isPrintableKey(event)) {
        event.preventDefault();
        openSpotlight(event.key);
        return;
      }
      if (isMeta && event.key.toLowerCase() === "k") {
        event.preventDefault();
        openSpotlight();
      }
      if (isMeta && event.key.toLowerCase() === "n") {
        event.preventDefault();
        openSpotlight();
      }
      if (event.key === "Escape" && spotlightOpen) {
        event.preventDefault();
        closeSpotlight();
      }
      if (!spotlightOpen && isMeta && queries.length && event.key === "ArrowUp") {
        event.preventDefault();
        const index = queries.findIndex((query) => query.id === activeQueryId);
        const next = queries[Math.max(0, index - 1)];
        if (next) setActiveQueryId(next.id);
      }
      if (!spotlightOpen && isMeta && queries.length && event.key === "ArrowDown") {
        event.preventDefault();
        const index = queries.findIndex((query) => query.id === activeQueryId);
        const next = queries[Math.min(queries.length - 1, index + 1)];
        if (next) setActiveQueryId(next.id);
      }
      if (!spotlightOpen && isMeta && event.key.toLowerCase() === "w" && activeQueryId) {
        event.preventDefault();
        handleCloseTab(activeQueryId);
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activeQueryId, closeSpotlight, handleCloseTab, isPrintableKey, layoutMode, openSpotlight, queries, spotlightOpen]);

  const handleSelectTab = (queryId) => {
    setActiveQueryId(queryId);
    setPreviewQueryId(null);
  };

  const handlePreviewTab = (queryId) => {
    if (previewTimerRef.current) window.clearTimeout(previewTimerRef.current);
    if (!queryId) {
      setPreviewQueryId(null);
      return;
    }
    previewTimerRef.current = window.setTimeout(() => setPreviewQueryId(queryId), 500);
  };

  const startRecording = async () => {
    if (loading || recording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = getRecordingMimeType();
      recordingMimeRef.current = mimeType;
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      mediaRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data?.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        setRecording(false);
        const blob = new Blob(
          chunksRef.current,
          { type: recorder.mimeType || recordingMimeRef.current || "audio/webm" },
        );
        mediaRef.current = null;
        chunksRef.current = [];
        if (blob.size < 1024) {
          setError("Recording was too short. Hold the microphone a little longer and try again.");
          return;
        }
        await sendVoice(blob);
      };
      recorder.start(250);
      setRecording(true);
    } catch (err) {
      setError("Microphone access denied");
    }
  };

  const stopRecording = () => {
    const recorder = mediaRef.current;
    if (recorder?.state === "recording") {
      recorder.requestData();
      recorder.stop();
    }
  };

  const stopVoicePlayback = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setVoicePlaying(false);
  };

  const sendVoice = async (blob) => {
    stopVoicePlayback();
    setLoading(true);
    setLoadingStage("Preparing voice response...");
    setError(null);
    const form = new FormData();
    const mimeType = blob.type || recordingMimeRef.current || "audio/webm";
    const extension = recordingExtension(mimeType);
    form.append("audio", blob, `recording.${extension}`);
    form.append("session_id", sessionId);

    try {
      const res = await fetch(`${API_BASE}/voice`, { method: "POST", body: form });
      if (!res.ok) throw new Error(await parseApiError(res, `Voice error: ${res.status}`));

      const transcript = decodeHeader(
        res.headers.get("X-Transcript-B64"),
        res.headers.get("X-Transcript"),
        "Voice message",
      );
      const responseText = decodeHeader(
        res.headers.get("X-Response-B64"),
        res.headers.get("X-Response"),
        "Processing...",
      );

      const audioBlob = await res.blob();
      const url = URL.createObjectURL(audioBlob);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => {
        URL.revokeObjectURL(url);
        audioRef.current = null;
        setVoicePlaying(false);
      };
      setVoicePlaying(true);
      await audio.play();

      const queryId = Date.now();
      setQueries((prev) => [{
        id: queryId,
        question: `🎤 ${transcript}`,
        createdAt: Date.now(),
        status: "complete",
        vizType: null,
        response: {
          text: responseText,
          visualization: null,
          suggestions: [],
        },
      }, ...prev]);
      setActiveQueryId(queryId);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setLoadingStage(null);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem(QUERIES_STORAGE_KEY);
    localStorage.removeItem("ooa_messages");
    localStorage.removeItem("ooa_session_id");
    onLogout?.();
  };

  return (
    <div className={shellClassName}>
      <AnimatedBackground />
      <FloatingChrome
        user={user}
        onLogout={handleLogout}
        soundEnabled={soundEnabled}
        volume={volume}
        onToggleSound={toggleSound}
        onVolumeChange={updateVolume}
      />

      {layoutMode !== "welcome" ? (
        <LeftSidebar onSelectQuery={(query) => openSpotlight(query)} compact />
      ) : null}

      <div className="ooa-layout__main">
        {layoutMode === "welcome" ? (
          <WelcomeScreen
            compact
            onOpenSpotlight={() => openSpotlight()}
            onSeedQuery={(query) => openSpotlight(query)}
          />
        ) : null}

        {layoutMode === "typing" ? (
          <SpotlightInput
            input={input}
            loading={loading}
            recording={recording}
            voicePlaying={voicePlaying}
            rtlInput={isArabic(input)}
            onInputChange={handleInputChange}
            onKeyDown={handleInputKeyDown}
            onSend={() => sendMessage(input)}
            onStartRecording={startRecording}
            onStopRecording={stopRecording}
            onStopVoicePlayback={stopVoicePlayback}
            onSelectSuggestion={sendMessage}
          />
        ) : null}

        {layoutMode === "generating" || layoutMode === "viewing" ? (
          <CenterStage
            query={activeQuery}
            loading={layoutMode === "generating"}
            loadingStage={loadingStage}
            pendingVizType={pendingVizType}
            toolSteps={toolSteps}
            onSuggestion={sendMessage}
          />
        ) : null}

        {layoutMode === "viewing" ? (
          <NewQuestionButton onClick={() => openSpotlight()} />
        ) : null}
      </div>

      {queries.length ? (
        <>
          <div className="ooa-history-rail">
            <button
              type="button"
              className="ooa-history-rail__toggle"
              aria-expanded={historyOpen}
              aria-controls="ooa-query-history"
              onClick={() => setHistoryOpen((open) => !open)}
            >
              <span aria-hidden="true">{historyOpen ? "›" : "‹"}</span>
              <span className="ooa-history-rail__label">Queries</span>
            </button>
          </div>
          <RightSidebar
            id="ooa-query-history"
            open={historyOpen}
            queries={queries}
            activeQueryId={activeQueryId}
            previewQueryId={previewQueryId}
            onSelect={handleSelectTab}
            onPreview={handlePreviewTab}
            onClose={handleCloseTab}
            onReask={sendMessage}
          />
        </>
      ) : null}

      {error ? (
        <div className="ooa-error-banner ooa-error-banner--floating">
          <span>⚠ {error}</span>
          <button type="button" onClick={() => setError(null)}>×</button>
        </div>
      ) : null}
    </div>
  );
}
