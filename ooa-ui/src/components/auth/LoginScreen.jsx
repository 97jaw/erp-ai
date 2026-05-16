import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import AnimatedBackground from "../background/AnimatedBackground";
import ThemeToggle from "../common/ThemeToggle";
import FeatureShowcase from "../layout/FeatureShowcase";
import { sound } from "../common/SoundManager";

const API_BASE = "http://localhost:8000";

const LOADING_MESSAGES = [
  "Connecting to Odoo...",
  "Verifying your File ID...",
  "Preparing your workspace...",
];

const parseLoginError = (body, fallback) => {
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) {
    return body.detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
  }
  if (typeof body?.message === "string") return body.message;
  return fallback;
};

export default function LoginScreen({ onAuthenticated }) {
  const [fileId, setFileId] = useState("");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [loadingIndex, setLoadingIndex] = useState(0);
  const [welcome, setWelcome] = useState({
    title: "Welcome",
    name: "",
    message: "",
    language: "en",
  });

  const normalizedFileId = useMemo(() => fileId.trim(), [fileId]);
  const canSubmit = normalizedFileId.length > 0;

  const submit = async () => {
    if (status === "loading") return;

    if (!normalizedFileId) {
      setError("Enter your File ID.");
      return;
    }

    setError("");
    setStatus("loading");
    setLoadingIndex(0);

    const interval = window.setInterval(() => {
      setLoadingIndex((current) => (current + 1) % LOADING_MESSAGES.length);
    }, 900);

    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: normalizedFileId }),
      });

      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(parseLoginError(body, "File ID not recognized"));
      }

      setWelcome({
        title: body.welcome_title || "Welcome",
        name: body.user_name || "",
        message: body.welcome_message || "Your workspace is ready.",
        language: body.language || "en",
      });
      setStatus("success");
      await sound.play(body.language === "ar" ? "login-success-ar" : "login-success-en");
      window.setTimeout(() => {
        onAuthenticated({
          sessionId: body.session_id,
          userName: body.user_name,
          language: body.language,
          fileId: body.file_id || normalizedFileId,
          welcomeTitle: body.welcome_title,
          welcomeMessage: body.welcome_message,
        });
      }, 2200);
    } catch (err) {
      setStatus("error");
      setError(err.message || "Sorry, that File ID was not recognized");
      await sound.play("login-fail-en", { volume: 0.45 });
      window.setTimeout(() => setStatus("idle"), 1800);
    } finally {
      window.clearInterval(interval);
    }
  };

  return (
    <motion.div
      className="ooa-app-shell ooa-layout ooa-layout--welcome ooa-login-screen"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.45 }}
    >
      <AnimatedBackground />
      <motion.div
        className="ooa-login-screen__theme"
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <ThemeToggle />
      </motion.div>

      <div className="ooa-layout__main">
        <section className="ooa-welcome-screen" aria-label="Sign in">
          <motion.div
            className="ooa-welcome-screen__hero"
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45 }}
          >
            <motion.div
              className="ooa-welcome-screen__rule"
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ duration: 0.8, delay: 0.1 }}
            />
            <h1 className="ooa-welcome-screen__title">Welcome to Elrace AI</h1>
            <p className="ooa-welcome-screen__subtitle">Your Intelligent ERP Companion</p>
            <motion.div
              className="ooa-welcome-screen__rule"
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ duration: 0.8, delay: 0.2 }}
            />
          </motion.div>

          <FeatureShowcase />

          <div className="ooa-login-spotlight">
            <AnimatePresence mode="wait">
              {status === "loading" ? (
                <motion.div
                  key="loading"
                  className="ooa-login-spotlight__panel"
                  initial={{ opacity: 0, scale: 0.96 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.98 }}
                >
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                    className="ooa-login-spotlight__spinner"
                  />
                  <motion.div
                    key={loadingIndex}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="ooa-login-spotlight__status"
                  >
                    {LOADING_MESSAGES[loadingIndex]}
                  </motion.div>
                </motion.div>
              ) : status === "success" ? (
                <motion.div
                  key="success"
                  className="ooa-login-spotlight__panel"
                  initial={{ opacity: 0, scale: 0.92 }}
                  animate={{ opacity: 1, scale: 1 }}
                >
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: [0, 1.15, 1] }}
                    transition={{ duration: 0.55, ease: "easeOut" }}
                    className="ooa-login-spotlight__success"
                  >
                    ✓
                  </motion.div>
                  <div className="ooa-login-spotlight__eyebrow">{welcome.title}</div>
                  <motion.div
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="ooa-login-spotlight__name"
                  >
                    {welcome.name}
                  </motion.div>
                  <motion.div
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.32 }}
                    className="ooa-login-spotlight__message"
                  >
                    {welcome.message}
                  </motion.div>
                </motion.div>
              ) : (
                <motion.div
                  key="form"
                  className="ooa-login-spotlight__panel"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                >
                  <label className="ooa-login-spotlight__label" htmlFor="ooa-file-id">
                    Enter your File ID
                  </label>
                  <motion.div
                    className="ooa-login-spotlight__row"
                    animate={status === "error" ? { x: [0, -8, 8, -6, 6, 0] } : { x: 0 }}
                    transition={{ duration: 0.45 }}
                  >
                    <input
                      id="ooa-file-id"
                      className="ooa-login-spotlight__input"
                      value={fileId}
                      onChange={(event) => setFileId(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") submit();
                      }}
                      placeholder="2721"
                      autoComplete="off"
                      inputMode="numeric"
                      autoFocus
                    />
                    <button
                      type="button"
                      className="ooa-send-btn"
                      disabled={!canSubmit}
                      onClick={submit}
                    >
                      →
                    </button>
                  </motion.div>
                  <div className="ooa-login-spotlight__hint">
                    Use your Elrace File ID to continue.
                  </div>
                  {error ? (
                    <motion.div
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="ooa-login-spotlight__error"
                    >
                      {error}
                    </motion.div>
                  ) : null}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <motion.div
            className="ooa-welcome-screen__dots"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.45 }}
            aria-hidden="true"
          >
            <span className="ooa-welcome-screen__dot ooa-welcome-screen__dot--active" />
            <span className="ooa-welcome-screen__dot" />
            <span className="ooa-welcome-screen__dot" />
            <span className="ooa-welcome-screen__dot" />
            <span className="ooa-welcome-screen__dot" />
          </motion.div>
        </section>
      </div>
    </motion.div>
  );
}
