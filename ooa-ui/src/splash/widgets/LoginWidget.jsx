import { useMemo, useState } from "react";
import { API_BASE } from "../../config/api";

const parseLoginError = (body, fallback) => {
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) {
    return body.detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
  }
  if (typeof body?.message === "string") return body.message;
  return fallback;
};

export default function LoginWidget({ onSubmit, onMfaRequired, inputRef }) {
  const [fileId, setFileId] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [mfaToken, setMfaToken] = useState("");
  const [mfaMode, setMfaMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const normalizedFileId = useMemo(() => fileId.trim(), [fileId]);
  const canSubmit = normalizedFileId.length > 0;
  const canSubmitMfa = mfaCode.trim().length >= 6;

  const submitLogin = async () => {
    if (loading || !canSubmit) {
      if (!canSubmit) setError("Enter your File ID.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: normalizedFileId }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(parseLoginError(body, "File ID not recognized"));

      if (body.mfa_required && body.mfa_token) {
        setMfaToken(body.mfa_token);
        setMfaMode(true);
        onMfaRequired?.(body);
        return;
      }

      await onSubmit?.(body, normalizedFileId);
    } catch (err) {
      setError(err.message || "File ID not recognized");
    } finally {
      setLoading(false);
    }
  };

  const submitMfa = async () => {
    if (loading || !canSubmitMfa) return;
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/mfa/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mfa_token: mfaToken, code: mfaCode.trim() }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(parseLoginError(body, "Invalid MFA code"));
      await onSubmit?.(body, normalizedFileId);
    } catch (err) {
      setError(err.message || "Invalid MFA code");
    } finally {
      setLoading(false);
    }
  };

  if (mfaMode) {
    return (
      <article className="splash-widget splash-login-widget" ref={inputRef}>
        <h3 className="splash-widget__title">🔐 Sign in</h3>
        <p className="splash-widget__desc">Enter the 6-digit code from your authenticator app.</p>
        <label className="splash-login-widget__label" htmlFor="splash-mfa-code">
          Authenticator code
        </label>
        <input
          id="splash-mfa-code"
          className={`splash-login-widget__input${error ? " splash-login-widget__input--error" : ""}`}
          value={mfaCode}
          onChange={(event) => setMfaCode(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") submitMfa();
          }}
          placeholder="000000"
          inputMode="numeric"
          autoComplete="one-time-code"
          autoFocus
        />
        <button
          type="button"
          className="splash-login-widget__submit"
          disabled={!canSubmitMfa || loading}
          onClick={submitMfa}
        >
          {loading ? "Verifying..." : "Verify →"}
        </button>
        {error ? <p className="splash-login-widget__error">{error}</p> : null}
      </article>
    );
  }

  return (
    <article className="splash-widget splash-login-widget" ref={inputRef}>
      <h3 className="splash-widget__title">🔐 Sign in</h3>
      <p className="splash-login-widget__welcome">Welcome to Elrace AI</p>
      <p className="splash-widget__desc">Your Intelligent ERP Companion</p>

      <label className="splash-login-widget__label" htmlFor="splash-file-id">
        File ID
      </label>
      <input
        id="splash-file-id"
        className={`splash-login-widget__input${error ? " splash-login-widget__input--error" : ""}`}
        value={fileId}
        onChange={(event) => setFileId(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") submitLogin();
        }}
        placeholder="Enter your File ID"
        autoComplete="off"
        inputMode="numeric"
      />
      <p className="splash-login-widget__example">e.g., 2721</p>

      <button
        type="button"
        className="splash-login-widget__submit"
        disabled={!canSubmit || loading}
        onClick={submitLogin}
      >
        {loading ? "Verifying..." : "Sign In →"}
      </button>

      <p className="splash-login-widget__footer">Use your Elrace File ID to continue</p>
      {error ? <p className="splash-login-widget__error">{error}</p> : null}
    </article>
  );
}
