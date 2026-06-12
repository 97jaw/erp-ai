import { useCallback, useEffect, useRef, useState } from "react";
import { sound } from "../common/SoundManager";
import { useSoundSettings } from "../../hooks/useSoundSettings";
import {
  API_BASE,
  decodeHeader,
  getChatThreadId,
  getRecordingMimeType,
  hasRenderableVisualization,
  isArabic,
  normalizeVisualization,
  parseApiError,
  recordingExtension,
  rotateChatThreadId,
  setChatThreadId,
  stripVisualization,
} from "../../utils/chat";
import {
  listPastConversations,
  loadConversationById,
  loadConversationHistory,
  deleteConversation,
  shouldResetChatAfterDelete,
} from "../../utils/chatHistory";
import { authFetch } from "../../config/api";
import WelcomeScreen from "../layout/WelcomeScreen";
import { VisualizePanel, useVisualizePanel } from "../../visualize";
import "../../visualize/styles/visualize.css";
import MainTopBar from "../../main/topbar/MainTopBar";
import QuickActionsSidebar from "../../main/sidebar/QuickActionsSidebar";
import ChatsSheet from "../../main/sidebar/ChatsSheet";
import ChatScrollView from "../../main/chat/ChatScrollView";
import ChatInputBar from "../../main/chat/ChatInputBar";
import DeepThinkConsentModal from "../../main/chat/DeepThinkConsentModal";
import ComingSoonFeatureModal from "../../main/chat/ComingSoonFeatureModal";
import VoiceStatusBanner from "../../main/chat/VoiceStatusBanner";
import { AuditPanel } from "../../audit";
import "../../audit/styles/audit.css";
import { buildClarificationQuery, buildConfirmedEntities } from "../../utils/clarify";
import { apiFetch } from "../../config/api";

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

export default function ChatScreen({
  user,
  initialSpotlightQuery = "",
  initialMainView = "chat",
  onLogout,
}) {
  const [chatThreadId, setChatThreadIdState] = useState(() => getChatThreadId());
  const { enabled: soundEnabled, volume, toggleEnabled: toggleSound, updateVolume } = useSoundSettings();
  const [queries, setQueries] = useState(loadStoredQueries);
  const [activeQueryId, setActiveQueryId] = useState(() => loadStoredQueries()[0]?.id || null);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [pastChats, setPastChats] = useState([]);
  const [pastChatsLoading, setPastChatsLoading] = useState(false);
  const [pastChatsError, setPastChatsError] = useState(null);
  const [input, setInput] = useState("");
  const [mainView, setMainView] = useState(
    () => (initialMainView === "audit" ? "audit" : "chat"),
  );
  const [sidebarExpanded, setSidebarExpanded] = useState(true);
  const [deepThinkConsent, setDeepThinkConsent] = useState(null);
  const [dashboardModalOpen, setDashboardModalOpen] = useState(false);
  const [chatsSheetOpen, setChatsSheetOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [voicePhase, setVoicePhase] = useState("idle");
  const [error, setError] = useState(null);
  const [loadingStage, setLoadingStage] = useState(null);
  const [toolSteps, setToolSteps] = useState([]);
  const [pendingVizType, setPendingVizType] = useState(null);
  const [voicePlaying, setVoicePlaying] = useState(false);
  const [loadingMoreSuggestions, setLoadingMoreSuggestions] = useState(false);
  const [deepThink, setDeepThink] = useState(false);
  const [deepThinkEligible, setDeepThinkEligible] = useState(false);
  const mediaRef = useRef(null);
  const audioRef = useRef(null);
  const chunksRef = useRef([]);
  const recordingMimeRef = useRef("");
  const chatInputRef = useRef(null);

  const visualize = useVisualizePanel();

  const hasChat = queries.length > 0 || loading;
  const vizBorderState = visualize.isDraggingFromChat || visualize.isDraggingOver
    ? "active"
    : visualize.droppedItems.length > 0
      ? "active"
      : "inactive";

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

  const fetchPastChats = useCallback(async () => {
    if (!user) return;
    setPastChatsLoading(true);
    setPastChatsError(null);
    try {
      const list = await listPastConversations(30);
      setPastChats(list);
    } catch (err) {
      setPastChatsError(err.message || "Could not load past chats");
    } finally {
      setPastChatsLoading(false);
    }
  }, [user]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const local = loadStoredQueries();
      if (local.length > 0) {
        setQueries(local);
        setActiveQueryId(local[0]?.id || null);
        if (user) fetchPastChats();
        return;
      }
      if (!user) return;
      try {
        const { queries: restored, conversationId } = await loadConversationHistory();
        if (!cancelled && restored.length > 0) {
          setQueries(restored);
          setActiveQueryId(restored[0]?.id || null);
          setActiveConversationId(conversationId || null);
          setChatThreadIdState(getChatThreadId());
        }
        if (!cancelled) fetchPastChats();
      } catch {
        /* offline or auth not ready */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, fetchPastChats]);

  useEffect(() => {
    if (sidebarExpanded && user) {
      fetchPastChats();
    }
  }, [sidebarExpanded, user, fetchPastChats]);

  const switchToChat = useCallback(() => {
    setMainView("chat");
  }, []);

  const handleLoadPastChat = useCallback(async (conversation) => {
    if (!conversation?.id) return;
    setMainView("chat");
    setError(null);
    setPastChatsLoading(true);
    try {
      const loaded = await loadConversationById(conversation.id);
      if (loaded.threadId) {
        setChatThreadId(loaded.threadId);
        setChatThreadIdState(loaded.threadId);
      }
      setQueries(loaded.queries);
      setActiveQueryId(loaded.queries[0]?.id || null);
      setActiveConversationId(loaded.conversationId);
      visualize.clearItems?.();
    } catch (err) {
      setError(err.message || "Could not open this chat");
    } finally {
      setPastChatsLoading(false);
    }
  }, [visualize]);

  const handleNewChat = useCallback(async () => {
    const previousThread = chatThreadId;
    try {
      await authFetch(`/session/${encodeURIComponent(previousThread)}`, {
        method: "DELETE",
      });
    } catch {
      /* best-effort */
    }
    const nextThread = rotateChatThreadId();
    setChatThreadIdState(nextThread);
    setQueries([]);
    setActiveQueryId(null);
    setActiveConversationId(null);
    setInput("");
    setError(null);
    visualize.clearItems?.();
    fetchPastChats();
  }, [chatThreadId, fetchPastChats, visualize]);

  const handleDeleteChat = useCallback(async (conversation) => {
    if (!conversation?.id) return;
    const title = (conversation.title || "Untitled chat").trim();
    const confirmed = window.confirm(
      `Delete "${title}"? This cannot be undone.`,
    );
    if (!confirmed) return;

    setPastChatsLoading(true);
    setPastChatsError(null);
    try {
      await deleteConversation(conversation.id, {
        externalSessionKey: conversation.external_session_key,
      });
      const resetActive = shouldResetChatAfterDelete(conversation, {
        activeConversationId,
        chatThreadId,
      });
      if (resetActive) {
        await handleNewChat();
      } else {
        setPastChats((prev) => prev.filter((item) => item.id !== conversation.id));
        await fetchPastChats();
      }
    } catch (err) {
      setError(err.message || "Could not delete this chat");
    } finally {
      setPastChatsLoading(false);
    }
  }, [
    activeConversationId,
    chatThreadId,
    fetchPastChats,
    handleNewChat,
  ]);

  const focusInput = useCallback((seed = "") => {
    setMainView("chat");
    if (seed) setInput(seed);
    window.requestAnimationFrame(() => {
      chatInputRef.current?.focus();
    });
  }, []);

  const handleSidebarNav = useCallback(
    (item) => {
      setMainView("chat");
      if (item?.action === "focus") {
        focusInput();
      } else if (item?.action === "chat-list") {
        setChatsSheetOpen(true);
      }
    },
    [focusInput],
  );

  const openAuditView = useCallback(() => {
    setMainView("audit");
    setChatsSheetOpen(false);
    visualize.closePanel();
  }, [visualize]);

  const handleToggleVisualize = useCallback(() => {
    setMainView("chat");
    visualize.togglePanel();
  }, [visualize]);

  useEffect(() => {
    if (!initialSpotlightQuery?.trim()) return;
    focusInput(initialSpotlightQuery);
  }, [initialSpotlightQuery, focusInput]);

  const updateQuery = useCallback((queryId, patch) => {
    setQueries((prev) => prev.map((query) => (
      query.id === queryId ? { ...query, ...patch } : query
    )));
  }, []);

  // Deep Think button is conditional: only shown when the typed query is
  // detected as financial / Odoo-data related (cheap keyword check, debounced).
  useEffect(() => {
    const trimmed = input.trim();
    if (!trimmed || trimmed.length < 3) {
      setDeepThinkEligible(false);
      setDeepThink(false);
      return undefined;
    }
    const timer = setTimeout(async () => {
      try {
        const payload = await apiFetch("/deep-think/eligibility", {
          method: "POST",
          body: JSON.stringify({ message: trimmed }),
        });
        const eligible = Boolean(payload?.eligible);
        setDeepThinkEligible(eligible);
        if (!eligible) setDeepThink(false);
      } catch {
        /* keep current state on transient errors */
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [input]);

  const sendMessage = useCallback(async (text, options = {}) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    const useDeepThink = options.deepThink !== undefined
      ? Boolean(options.deepThink)
      : deepThink;

    setError(null);
    setInput("");
    setDeepThink(false);
    sound.play("message-send", { volume: 0.35 });

    const queryId = Date.now();
    let streamDone = false;
    const createdAt = Date.now();
    const nextQuery = {
      id: queryId,
      question: trimmed,
      createdAt,
      status: "generating",
      vizType: null,
      deepThink: useDeepThink,
      response: {
        text: "",
        visualization: null,
        suggestions: [],
      },
    };

    setQueries((prev) => [nextQuery, ...prev]);
    setActiveQueryId(queryId);
    setLoading(true);
    setLoadingStage(useDeepThink ? "Deep thinking — pulling live data..." : "Preparing your answer...");
    setPendingVizType(null);
    setToolSteps([]);

    try {
      const res = await authFetch("/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          session_id: chatThreadId,
          skip_clarification: Boolean(options.skipClarification),
          confirmed_entities: options.confirmedEntities || [],
          deep_think: useDeepThink,
        }),
      });

      if (!res.ok) {
        const detail = await parseApiError(res, `Server error: ${res.status}`);
        if (res.status === 401) {
          throw new Error("Session expired. Please sign in again.");
        }
        throw new Error(detail);
      }

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
            } else if (data.type === "clarify") {
              setLoading(false);
              setLoadingStage(null);
              updateQuery(queryId, {
                status: "awaiting_clarification",
                response: {
                  text: data.clarification?.question || "",
                  clarification: data.clarification,
                  visualization: null,
                  suggestions: [],
                },
              });
            } else if (data.type === "error") {
              const message = data.message || "Could not reach Odoo.";
              setError(message);
              updateQuery(queryId, {
                status: "error",
                response: {
                  text: message,
                  visualization: null,
                  suggestions: [],
                },
              });
              setLoading(false);
              setLoadingStage(null);
            } else if (data.type === "done") {
              if (streamDone) continue;
              streamDone = true;
              sound.play("message-receive", { volume: 0.3 });
              const visualization = hasRenderableVisualization(data.visualization)
                ? normalizeVisualization(data.visualization)
                : null;
              const serverText = typeof data.text === "string"
                ? stripVisualization(data.text)
                : stripVisualization(streamedText);
              const finalText = serverText || stripVisualization(streamedText);
              if (data.awaiting_clarification && data.clarification) {
                updateQuery(queryId, {
                  status: "awaiting_clarification",
                  response: {
                    text: finalText || data.clarification?.question || "",
                    clarification: data.clarification,
                    visualization: null,
                    suggestions: [],
                  },
                });
              } else {
                updateQuery(queryId, {
                  status: "complete",
                  vizType: visualization?.visual_type || null,
                  response: {
                    text: finalText,
                    visualization,
                    suggestions: data.suggestions || [],
                    suggestionMeta: data.suggestion_meta || null,
                    clarification: null,
                    deepThinkAvailable: Boolean(data.deep_think_available),
                  },
                });
                if (data.deep_think_available) {
                  setDeepThinkEligible(true);
                }
                /* Visualize opens only via top-bar / ⌘V — not auto on response */
              }
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
  }, [loading, chatThreadId, updateQuery, visualize, deepThink]);

  const requestSend = useCallback((text, options = {}) => {
    const trimmed = String(text || "").trim();
    if (!trimmed || loading) return;
    const useDeepThink = options.deepThink !== undefined
      ? Boolean(options.deepThink)
      : deepThink;
    if (useDeepThink) {
      setDeepThinkConsent({
        mode: "send",
        payload: { text: trimmed, options: { ...options, deepThink: true } },
      });
      return;
    }
    sendMessage(trimmed, options);
  }, [deepThink, loading, sendMessage]);

  const handleDeepThinkToggle = useCallback(() => {
    if (deepThink) {
      setDeepThink(false);
      return;
    }
    setDeepThinkConsent({ mode: "enable" });
  }, [deepThink]);

  const handleDeepThinkConsentConfirm = useCallback(() => {
    if (!deepThinkConsent) return;
    if (deepThinkConsent.mode === "enable") {
      setDeepThink(true);
      setDeepThinkConsent(null);
      return;
    }
    const { text, options } = deepThinkConsent.payload || {};
    setDeepThinkConsent(null);
    if (text) sendMessage(text, options || {});
  }, [deepThinkConsent, sendMessage]);

  const handleClarificationSelect = useCallback((option, originalQuery) => {
    // Clarifications continue the original turn — preserve its Deep Think mode.
    // Options flagged deep_think (period presets on report queries) force it on
    // so one click fetches the real Odoo figures.
    const sourceQuery = queries.find((item) => item.question === originalQuery);
    const resumeDeepThink = Boolean(sourceQuery?.deepThink) || Boolean(option?.deep_think);
    const confirmedEntities = buildConfirmedEntities(option);
    if (confirmedEntities.length > 0) {
      requestSend(originalQuery, {
        skipClarification: true,
        confirmedEntities,
        deepThink: resumeDeepThink,
      });
      return;
    }
    if (option?.action === "try_different_name") {
      setInput("");
      setLoading(false);
      setLoadingStage(null);
      focusInput("Try a different project name or WO number…");
      return;
    }
    const enriched = buildClarificationQuery(originalQuery, option);
    requestSend(enriched, { skipClarification: true, deepThink: resumeDeepThink });
  }, [requestSend, focusInput, queries]);

  const handleShowMoreSuggestions = useCallback(async (queryId) => {
    const query = queries.find((item) => item.id === queryId);
    const token = query?.response?.suggestionMeta?.token;
    if (!token || loadingMoreSuggestions) return;

    setLoadingMoreSuggestions(true);
    try {
      const payload = await apiFetch("/suggestions/more", {
        method: "POST",
        body: JSON.stringify({ token }),
      });
      updateQuery(queryId, {
        response: {
          ...query.response,
          suggestions: payload.suggestions || [],
          suggestionMeta: payload.suggestion_meta || query.response.suggestionMeta,
        },
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingMoreSuggestions(false);
    }
  }, [loadingMoreSuggestions, queries, updateQuery]);

  const clearConversation = useCallback(async () => {
    try {
      await authFetch(`/session/${encodeURIComponent(chatThreadId)}`, {
        method: "DELETE",
      });
    } catch (error) {
      // best-effort backend reset
    }

    localStorage.removeItem(QUERIES_STORAGE_KEY);
    localStorage.removeItem("ooa_messages");
    localStorage.removeItem("ooa_suggestions_shown");
    const nextThread = rotateChatThreadId();
    setChatThreadIdState(nextThread);

    setQueries([]);
    setActiveQueryId(null);
    setActiveConversationId(null);
    setError(null);
    setLoading(false);
    setLoadingStage(null);
    setPendingVizType(null);
    setToolSteps([]);
    setInput("");
    fetchPastChats();
  }, [chatThreadId, fetchPastChats]);

  const handleInputChange = (event) => {
    setInput(event.target.value);
  };

  const handleInputKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      requestSend(input);
    }
    if (event.key === "Escape") {
      event.preventDefault();
      setInput("");
      chatInputRef.current?.blur();
    }
  };

  const startRecording = async () => {
    if (loading || recording || voicePhase === "transcribing" || voicePhase === "processing") return;
    try {
      setVoicePhase("recording");
      setError(null);
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
          setVoicePhase("idle");
          setError("Recording was too short. Hold the microphone a little longer and try again.");
          return;
        }
        setVoicePhase("transcribing");
        await sendVoice(blob);
      };
      recorder.start(250);
      setRecording(true);
    } catch (err) {
      setVoicePhase("idle");
      setRecording(false);
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
    setVoicePhase("transcribing");
    setLoadingStage("Transcribing your voice…");
    setError(null);
    const form = new FormData();
    const mimeType = blob.type || recordingMimeRef.current || "audio/webm";
    const extension = recordingExtension(mimeType);
    form.append("audio", blob, `recording.${extension}`);
    form.append("session_id", chatThreadId);

    try {
      const res = await authFetch("/voice", {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(await parseApiError(res, `Voice error: ${res.status}`));

      setVoicePhase("processing");
      setLoadingStage("Preparing your answer…");

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

      setInput(transcript);
      setVoicePhase("processing");

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
      setVoicePhase("idle");
    } finally {
      setLoading(false);
      setLoadingStage(null);
      setVoicePhase("idle");
    }
  };

  const handleLogout = () => {
    localStorage.removeItem(QUERIES_STORAGE_KEY);
    localStorage.removeItem("ooa_messages");
    onLogout?.();
  };

  const shellClass = [
    "ooa-main-shell-wrap",
    visualize.open ? "ooa-main-shell-wrap--viz-open" : "",
    sidebarExpanded ? "ooa-main-shell-wrap--sidebar-expanded" : "",
    `ooa-main-shell-wrap--viz-${vizBorderState}`,
  ].filter(Boolean).join(" ");

  return (
    <div className={shellClass}>
      <VisualizePanel
        open={visualize.open}
        borderState={vizBorderState}
        droppedItems={visualize.droppedItems}
        isDraggingOver={visualize.isDraggingOver}
        isDraggingFromChat={visualize.isDraggingFromChat}
        lastDropAt={visualize.lastDropAt}
        chatSessionId={chatThreadId}
        onToggle={visualize.togglePanel}
        onClose={visualize.closePanel}
        onDragOver={visualize.handleDragOver}
        onDragLeave={visualize.handleDragLeave}
        onDrop={visualize.handleDrop}
        onRemoveItem={visualize.removeItem}
        onClear={visualize.clearItems}
      />

      <div className="ooa-main-shell">
        <MainTopBar
          user={user}
          mainView={mainView}
          visualizeOpen={visualize.open}
          onLogout={handleLogout}
          onClearConversation={clearConversation}
          onNewChat={handleNewChat}
          onOpenAudit={openAuditView}
          onToggleVisualize={handleToggleVisualize}
          onBuildDashboard={() => setDashboardModalOpen(true)}
          onOpenChats={() => {
            switchToChat();
            setChatsSheetOpen(true);
          }}
          soundEnabled={soundEnabled}
          volume={volume}
          onToggleSound={toggleSound}
          onVolumeChange={updateVolume}
          onOpenSearch={() => focusInput()}
        />

        <ChatsSheet
          open={chatsSheetOpen}
          onClose={() => setChatsSheetOpen(false)}
          conversations={pastChats}
          loading={pastChatsLoading}
          error={pastChatsError}
          activeConversationId={activeConversationId}
          onSelect={handleLoadPastChat}
          onRefresh={fetchPastChats}
          onNewChat={handleNewChat}
          onDelete={handleDeleteChat}
        />

        <QuickActionsSidebar
          queries={queries}
          activeQueryId={activeQueryId}
          onNavAction={handleSidebarNav}
          onSelectHistory={(queryId) => {
            switchToChat();
            setActiveQueryId(queryId);
          }}
          onExpandedChange={setSidebarExpanded}
          pastChats={pastChats}
          pastChatsLoading={pastChatsLoading}
          pastChatsError={pastChatsError}
          activeConversationId={activeConversationId}
          onLoadPastChat={handleLoadPastChat}
          onRefreshPastChats={fetchPastChats}
          onNewChat={() => {
            switchToChat();
            handleNewChat();
          }}
          onDeleteChat={handleDeleteChat}
        />

        <main
          className={`ooa-main-chat${mainView === "audit" ? " ooa-main-chat--audit" : ""}`}
          id="ooa-chat-main"
        >
          <div
            className={`ooa-main-view-pane ooa-main-view-pane--audit${
              mainView !== "audit" ? " ooa-main-view-pane--hidden" : ""
            }`}
            aria-hidden={mainView !== "audit"}
          >
            <AuditPanel user={user} embedded />
          </div>
          <div
            className={`ooa-main-view-pane ooa-main-view-pane--chat${
              mainView !== "chat" ? " ooa-main-view-pane--hidden" : ""
            }`}
            aria-hidden={mainView !== "chat"}
          >
            {!hasChat ? (
              <WelcomeScreen
                onOpenSpotlight={() => focusInput()}
                onSeedQuery={(query) => {
                  if (typeof query === "string" && query.trim()) {
                    requestSend(query);
                  } else {
                    focusInput();
                  }
                }}
              />
            ) : (
              <ChatScrollView
                queries={queries}
                activeQueryId={activeQueryId}
                loading={loading}
                loadingStage={loadingStage}
                pendingVizType={pendingVizType}
                toolSteps={toolSteps}
                language={user?.language || "en"}
                onSuggestion={requestSend}
                onClarificationSelect={handleClarificationSelect}
                onClarificationSkip={handleClarificationSelect}
                onShowMoreSuggestions={() => handleShowMoreSuggestions(activeQueryId)}
                loadingMoreSuggestions={loadingMoreSuggestions}
                onVisualizeDragStart={visualize.notifyDragStart}
                onVisualizeDragEnd={visualize.notifyDragEnd}
              />
            )}
            <VoiceStatusBanner phase={voicePhase} />
            <div className="ooa-chat-input-dock">
              <ChatInputBar
                input={input}
                inputRef={chatInputRef}
                loading={loading}
                recording={recording}
                voicePhase={voicePhase}
                rtlInput={isArabic(input)}
                onInputChange={handleInputChange}
                onKeyDown={handleInputKeyDown}
                onSend={() => requestSend(input)}
                onStartRecording={startRecording}
                onStopRecording={stopRecording}
                onSelectSuggestion={requestSend}
                deepThink={deepThink}
                deepThinkEligible={deepThinkEligible}
                onToggleDeepThink={handleDeepThinkToggle}
              />
            </div>
          </div>
        </main>
      </div>

      {error ? (
        <div className="ooa-error-banner ooa-error-banner--floating" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)}>×</button>
        </div>
      ) : null}

      <DeepThinkConsentModal
        open={Boolean(deepThinkConsent)}
        mode={deepThinkConsent?.mode || "send"}
        onConfirm={handleDeepThinkConsentConfirm}
        onCancel={() => setDeepThinkConsent(null)}
      />

      <ComingSoonFeatureModal
        open={dashboardModalOpen}
        title="Build My Dashboard"
        body="Personalized executive dashboards are under development. You will be able to pin KPIs, projects, and reports here soon."
        onClose={() => setDashboardModalOpen(false)}
      />
    </div>
  );
}
