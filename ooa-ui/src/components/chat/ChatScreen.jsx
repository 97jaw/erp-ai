import { useCallback, useEffect, useRef, useState } from "react";
import { sound } from "../common/SoundManager";
import { useSoundSettings } from "../../hooks/useSoundSettings";
import {
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
import ComingSoonFeatureModal from "../../main/chat/ComingSoonFeatureModal";
import { AuditPanel } from "../../audit";
import "../../audit/styles/audit.css";
import { ReportsPanel } from "../../reports";
import "../../reports/reports.css";
import { buildClarificationQuery, buildConfirmedEntities } from "../../utils/clarify";
import { apiFetch } from "../../config/api";
import { withWelcomeTurn, WELCOME_TURN_ID } from "../../chat/welcomeTurn";

/** Agent-mode rebuild: main chat uses /agent/stream unless explicitly disabled. */
const USE_AGENT_STREAM = process.env.REACT_APP_USE_AGENT_STREAM !== "false";
const DOCUMENT_SCOPE_OPTION_IDS = new Set(["project", "agreement", "rfq", "record"]);

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
    () =>
      initialMainView === "audit"
        ? "audit"
        : initialMainView === "reports"
          ? "reports"
          : "chat",
  );
  const [sidebarExpanded, setSidebarExpanded] = useState(true);
  const [dashboardModalOpen, setDashboardModalOpen] = useState(false);
  const [chatsSheetOpen, setChatsSheetOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [voicePhase, setVoicePhase] = useState("idle");
  const [error, setError] = useState(null);
  const [loadingStage, setLoadingStage] = useState(null);
  const [toolSteps, setToolSteps] = useState([]);
  const [pendingVizType, setPendingVizType] = useState(null);
  const [loadingMoreSuggestions, setLoadingMoreSuggestions] = useState(false);
  const [deepThink, setDeepThink] = useState(false);
  const [deepThinkEligible, setDeepThinkEligible] = useState(false);
  const mediaRef = useRef(null);
  const audioRef = useRef(null);
  const chunksRef = useRef([]);
  const recordingMimeRef = useRef("");
  const chatInputRef = useRef(null);
  const sendingRef = useRef(false);

  const visualize = useVisualizePanel();

  const hasChat = queries.length > 0 || loading;
  const vizBorderState = visualize.isDraggingFromChat || visualize.isDraggingOver
    ? "active"
    : visualize.droppedItems.length > 0
      ? "active"
      : "inactive";

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
      if (!user) {
        if (local.length > 0) {
          setQueries(local);
          setActiveQueryId(local[0]?.id || null);
        }
        return;
      }
      try {
        const { queries: restored, conversationId, threadId } = await loadConversationHistory();
        const threadMatches = threadId === getChatThreadId();
        if (!cancelled && restored.length > 0 && (local.length === 0 || threadMatches)) {
          setQueries(restored);
          setActiveQueryId(restored[0]?.id || null);
          setActiveConversationId(conversationId || null);
          if (threadId) {
            setChatThreadId(threadId);
            setChatThreadIdState(threadId);
          }
        } else if (!cancelled && local.length > 0) {
          setQueries(local);
          setActiveQueryId(local[0]?.id || null);
        } else if (!cancelled) {
          setQueries(withWelcomeTurn([], user));
          setActiveQueryId(WELCOME_TURN_ID);
        }
        if (!cancelled) fetchPastChats();
      } catch {
        if (!cancelled && local.length > 0) {
          setQueries(local);
          setActiveQueryId(local[0]?.id || null);
        }
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
      setQueries(loaded.queries.length ? loaded.queries : withWelcomeTurn([], user));
      setActiveQueryId(loaded.queries[0]?.id || WELCOME_TURN_ID);
      setActiveConversationId(loaded.conversationId);
      visualize.clearItems?.();
    } catch (err) {
      setError(err.message || "Could not open this chat");
    } finally {
      setPastChatsLoading(false);
    }
  }, [visualize, user]);

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
    setQueries(withWelcomeTurn([], user));
    setActiveQueryId(WELCOME_TURN_ID);
    setActiveConversationId(null);
    setInput("");
    setError(null);
    visualize.clearItems?.();
    fetchPastChats();
  }, [chatThreadId, fetchPastChats, user, visualize]);

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

  const openAuditView = useCallback(() => {
    setMainView("audit");
    setChatsSheetOpen(false);
    visualize.closePanel();
  }, [visualize]);

  const openReportsView = useCallback(() => {
    setMainView("reports");
    setChatsSheetOpen(false);
    visualize.closePanel();
  }, [visualize]);

  const handleSidebarNav = useCallback(
    (item) => {
      if (item?.action === "reports") {
        setMainView("reports");
        setChatsSheetOpen(false);
        visualize.closePanel();
        return;
      }
      setMainView("chat");
      if (item?.action === "focus") {
        focusInput();
      } else if (item?.action === "chat-list") {
        setChatsSheetOpen(true);
      }
    },
    [focusInput, visualize],
  );

  const handleToggleVisualize = useCallback(() => {
    setMainView("chat");
    visualize.togglePanel();
  }, [visualize]);

  const handleSendToVisualize = useCallback(async (payload) => {
    setMainView("chat");
    visualize.openPanel();
    await visualize.addItem(payload);
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
        setDeepThink(eligible);
      } catch {
        /* keep current state on transient errors */
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [input]);

  const sendMessage = useCallback(async (text, options = {}) => {
    const trimmed = text.trim();
    if (!trimmed || loading || sendingRef.current) return;

    sendingRef.current = true;
    const useDeepThink = options.deepThink !== undefined
      ? Boolean(options.deepThink)
      : deepThink && deepThinkEligible;

    setError(null);
    setInput("");
    setDeepThink(false);
    sound.play("message-send", { volume: 0.35 });

    const queryId = Date.now();
    let streamDone = false;
    const createdAt = Date.now();
    const localUiBlocks = [];
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
      const res = await authFetch(USE_AGENT_STREAM ? "/agent/stream" : "/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          USE_AGENT_STREAM
            ? {
                message: trimmed,
                session_id: chatThreadId,
                agent_type: "chat",
                skip_clarification: Boolean(options.skipClarification),
                confirmed_entities: options.confirmedEntities || [],
                deep_think: useDeepThink,
                documents_scope: options.documentsScope || null,
              }
            : {
                message: trimmed,
                session_id: chatThreadId,
                skip_clarification: Boolean(options.skipClarification),
                confirmed_entities: options.confirmedEntities || [],
                deep_think: useDeepThink,
                documents_scope: options.documentsScope || null,
              },
        ),
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
            } else if (data.type === "ui_block" && data.block) {
              localUiBlocks.push(data.block);
              updateQuery(queryId, {
                response: {
                  text: stripVisualization(streamedText),
                  visualization: null,
                  suggestions: [],
                  uiBlocks: [...localUiBlocks],
                },
              });
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
              const streamedStripped = stripVisualization(streamedText);
              const serverText = typeof data.text === "string"
                ? stripVisualization(data.text)
                : streamedStripped;
              // Prefer whichever is longer — done.text can be shorter than
              // streamedText when Claude emits text across multiple tool-use
              // rounds (only the final round lands in done.text on the server).
              const finalText = (streamedStripped.length > serverText.length ? streamedStripped : serverText) || streamedStripped;
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
                    suggestionDetails: data.suggestion_details || null,
                    suggestionMeta: data.suggestion_meta || null,
                    uiBlocks: data.ui_blocks?.length ? data.ui_blocks : [...localUiBlocks],
                    clarification: null,
                    deepThinkAvailable: Boolean(data.deep_think_available),
                  },
                });
                if (data.deep_think_available) {
                  setDeepThinkEligible(true);
                }
                if (data.conversation_id) {
                  setActiveConversationId(data.conversation_id);
                }
                fetchPastChats();
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
      sendingRef.current = false;
      setLoading(false);
      setLoadingStage(null);
      setPendingVizType(null);
      setToolSteps([]);
    }
  }, [loading, chatThreadId, updateQuery, deepThink, deepThinkEligible, fetchPastChats]);

  const requestSend = useCallback((text, options = {}) => {
    const trimmed = String(text || "").trim();
    if (!trimmed || loading) return;
    sendMessage(trimmed, options);
  }, [loading, sendMessage]);

  const handleDeepThinkToggle = useCallback(() => {
    if (!deepThinkEligible || loading) return;
    setDeepThink((prev) => !prev);
  }, [deepThinkEligible, loading]);

  const handleSuggestionForQuery = useCallback((label, queryId) => {
    const query = queries.find((item) => item.id === queryId);
    const details = query?.response?.suggestionDetails;
    const match = Array.isArray(details)
      ? details.find((item) => item?.label === label)
      : null;
    requestSend(match?.query || label);
  }, [queries, requestSend]);

  const handleUiBlockAction = useCallback((action, sourceQuery) => {
    const label = typeof action === "string" ? action : action?.label || "";
    const option = typeof action === "object" ? action?.option : null;
    const optionId = option?.id;
    const confirmedEntities = [];
    if (optionId != null && /^\d+$/.test(String(optionId))) {
      confirmedEntities.push({
        type: "project",
        id: Number(optionId),
        name: option?.label || label,
      });
    }
    const originalQuery = sourceQuery?.question || "";
    const cleanLabel = label
      .replace(/^[\u{1F300}-\u{1FAFF}\s]+/u, "")
      .trim();
    const enriched = optionId != null && /^\d+$/.test(String(optionId))
      ? `${originalQuery} — ${cleanLabel}`.trim()
      : cleanLabel || label;
    const documentsScope = optionId != null && DOCUMENT_SCOPE_OPTION_IDS.has(String(optionId))
      ? String(optionId)
      : null;
    requestSend(enriched, {
      skipClarification: true,
      confirmedEntities,
      documentsScope,
      deepThink: Boolean(option?.deep_think),
    });
  }, [requestSend]);

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
      const text = String(event.currentTarget?.value || "").trim();
      if (!text || loading || sendingRef.current) return;
      setInput("");
      requestSend(text);
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
          setError("Recording was too short. Speak a little longer, then tap the mic again to finish.");
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

  const toggleRecording = async () => {
    if (recording || voicePhase === "recording") {
      stopRecording();
      return;
    }
    await startRecording();
  };

  const stopVoicePlayback = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
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
    // Pass deep_think state so voice queries honour the toggle like text queries do
    if (deepThink && deepThinkEligible) form.append("deep_think", "true");

    try {
      const res = await authFetch("/voice", {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(await parseApiError(res, `Voice error: ${res.status}`));

      setVoicePhase("processing");
      setLoadingStage(deepThink && deepThinkEligible ? "Deep thinking — pulling live data…" : "Preparing your answer…");

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

      // Helper: decode a Base64-encoded UTF-8 JSON header into a JS value
      const decodeB64Json = (header) => {
        if (!header) return null;
        try {
          const bytes = Uint8Array.from(atob(header), (c) => c.charCodeAt(0));
          return JSON.parse(new TextDecoder("utf-8").decode(bytes));
        } catch { return null; }
      };

      const voiceDeepThinkAvailable  = res.headers.get("X-Deep-Think-Available") === "true";
      const voiceAwaitingClarif      = res.headers.get("X-Awaiting-Clarification") === "true";
      const voiceClarification       = decodeB64Json(res.headers.get("X-Clarification-B64"));
      const voiceVisualization       = decodeB64Json(res.headers.get("X-Visualization-B64"));
      const voiceSuggestionMeta      = decodeB64Json(res.headers.get("X-Suggestion-Meta-B64"));

      let voiceSuggestions = [];
      try {
        const sugHeader = res.headers.get("X-Suggestions");
        if (sugHeader) voiceSuggestions = JSON.parse(sugHeader);
      } catch { /* ignore malformed header */ }

      const audioBlob = await res.blob();
      const url = URL.createObjectURL(audioBlob);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => {
        URL.revokeObjectURL(url);
        audioRef.current = null;
      };
      try {
        await audio.play();
      } catch {
        // TTS blocked after async /voice round-trip (autoplay policy). Text still lands in chat.
        URL.revokeObjectURL(url);
        audioRef.current = null;
      }

      // Clear the input bar and reset deep think toggle
      setInput("");
      setDeepThink(false);
      setVoicePhase("processing");

      if (voiceDeepThinkAvailable) setDeepThinkEligible(true);

      const queryId = Date.now();
      setQueries((prev) => [{
        id: queryId,
        question: `🎤 ${transcript}`,
        createdAt: Date.now(),
        status: voiceAwaitingClarif ? "awaiting_clarification" : "complete",
        vizType: voiceVisualization?.visual_type || null,
        response: {
          text: voiceAwaitingClarif
            ? (voiceClarification?.question || responseText)
            : responseText,
          visualization: voiceVisualization,
          suggestions: voiceSuggestions,
          suggestionMeta: voiceSuggestionMeta,
          clarification: voiceClarification,
          deepThinkAvailable: voiceDeepThinkAvailable,
        },
      }, ...prev]);
      setActiveQueryId(queryId);
    } catch (err) {
      const message = String(err?.message || "");
      if (
        message.includes("not allowed by the user agent")
        || message.includes("play()")
      ) {
        setError(null);
      } else {
        setError(message || "Voice request failed. Please try again.");
      }
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

  const isNonChatView = mainView === "audit" || mainView === "reports";

  const shellClass = [
    "ooa-main-shell-wrap",
    mainView === "audit" ? "ooa-main-shell-wrap--audit-view" : "",
    mainView === "reports" ? "ooa-main-shell-wrap--audit-view" : "", // reuse audit layout
    visualize.open && !isNonChatView ? "ooa-main-shell-wrap--viz-open" : "",
    sidebarExpanded ? "ooa-main-shell-wrap--sidebar-expanded" : "",
    !isNonChatView ? `ooa-main-shell-wrap--viz-${vizBorderState}` : "",
  ].filter(Boolean).join(" ");

  return (
    <div className={shellClass}>
      {!isNonChatView ? (
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
      ) : null}

      <div className="ooa-main-shell">
        <MainTopBar
          user={user}
          mainView={mainView}
          visualizeOpen={visualize.open}
          onLogout={handleLogout}
          onClearConversation={clearConversation}
          onNewChat={handleNewChat}
          onOpenAudit={openAuditView}
          onCloseAudit={switchToChat}
          onOpenReports={openReportsView}
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
          className={`ooa-main-chat${isNonChatView ? " ooa-main-chat--audit" : ""}`}
          id="ooa-chat-main"
        >
          <div
            className={`ooa-main-view-pane ooa-main-view-pane--audit${
              mainView !== "audit" ? " ooa-main-view-pane--hidden" : ""
            }`}
            aria-hidden={mainView !== "audit"}
          >
            <AuditPanel user={user} embedded onCloseToChat={switchToChat} />
          </div>
          <div
            className={`ooa-main-view-pane ooa-main-view-pane--audit${
              mainView !== "reports" ? " ooa-main-view-pane--hidden" : ""
            }`}
            aria-hidden={mainView !== "reports"}
          >
            <ReportsPanel user={user} embedded onCloseToChat={switchToChat} />
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
                onSuggestion={handleSuggestionForQuery}
                onUiBlockAction={handleUiBlockAction}
                onClarificationSelect={handleClarificationSelect}
                onClarificationSkip={handleClarificationSelect}
                onShowMoreSuggestions={() => handleShowMoreSuggestions(activeQueryId)}
                loadingMoreSuggestions={loadingMoreSuggestions}
                onVisualizeDragStart={visualize.notifyDragStart}
                onVisualizeDragEnd={visualize.notifyDragEnd}
                onSendToVisualize={handleSendToVisualize}
              />
            )}
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
                onToggleRecording={toggleRecording}
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

      <ComingSoonFeatureModal
        open={dashboardModalOpen}
        title="Build Dashboard"
        body="Personalized executive dashboards are under development. You will be able to pin KPIs, projects, and reports here soon."
        onClose={() => setDashboardModalOpen(false)}
      />
    </div>
  );
}
