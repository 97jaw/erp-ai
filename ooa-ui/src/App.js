import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import LoginScreen from "./components/auth/LoginScreen";
import ChatScreen from "./components/chat/ChatScreen";
import AdminApp from "./admin/AdminApp";
import { ThemeProvider } from "./theme/ThemeProvider";
import { AUTH_STORAGE_KEY, readStoredAuth } from "./config/api";

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
      accessToken: payload.sessionId,
      userName: payload.userName,
      language: payload.language,
      fileId: payload.fileId,
      welcomeTitle: payload.welcomeTitle,
      welcomeMessage: payload.welcomeMessage,
      roles: payload.roles || [],
      permissions: payload.permissions || [],
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
      <BrowserRouter>
        <a className="ooa-skip-link" href="#ooa-chat-main">
          Skip to chat
        </a>
        <Routes>
          <Route
            path="/admin/*"
            element={
              auth ? (
                <AdminApp user={auth} onLogout={handleLogout} />
              ) : (
                <Navigate to="/" replace />
              )
            }
          />
          <Route
            path="/*"
            element={
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
            }
          />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}
