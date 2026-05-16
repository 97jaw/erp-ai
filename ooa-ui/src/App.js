import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import LoginScreen from "./components/auth/LoginScreen";
import ChatScreen from "./components/chat/ChatScreen";
import { ThemeProvider } from "./theme/ThemeProvider";

const AUTH_STORAGE_KEY = "ooa_auth";

function readStoredAuth() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (error) {
    return null;
  }
}

export default function App() {
  const [auth, setAuth] = useState(() => readStoredAuth());

  useEffect(() => {
    if (!auth) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      return;
    }
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth));
    if (auth.sessionId) {
      localStorage.setItem("ooa_session_id", auth.sessionId);
    }
  }, [auth]);

  const handleAuthenticated = (payload) => {
    setAuth({
      sessionId: payload.sessionId,
      userName: payload.userName,
      language: payload.language,
      fileId: payload.fileId,
      welcomeTitle: payload.welcomeTitle,
      welcomeMessage: payload.welcomeMessage,
    });
  };

  const handleLogout = () => {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    localStorage.removeItem("ooa_messages");
    localStorage.removeItem("ooa_session_id");
    setAuth(null);
  };

  return (
    <ThemeProvider>
      <a className="ooa-skip-link" href="#ooa-chat-main">
        Skip to chat
      </a>
      <AnimatePresence mode="wait">
        {!auth ? (
          <motion.div
            key="login"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, x: -24 }}
            transition={{ duration: 0.35 }}
          >
            <LoginScreen onAuthenticated={handleAuthenticated} />
          </motion.div>
        ) : (
          <motion.div
            key="chat"
            initial={{ opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.45 }}
            style={{ height: "100%" }}
          >
            <ChatScreen sessionId={auth.sessionId} user={auth} onLogout={handleLogout} />
          </motion.div>
        )}
      </AnimatePresence>
    </ThemeProvider>
  );
}
