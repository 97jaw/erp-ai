import { useMemo, useState } from "react";
import { resolveApiBase } from "../config/api";

const parseLoginError = (body, fallback) => {
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) {
    return body.detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
  }
  if (typeof body?.message === "string") return body.message;
  return fallback;
};

export default function LoginInline({ onSubmit, formRef }) {
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
      const res = await fetch(`${resolveApiBase()}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: normalizedFileId }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(parseLoginError(body, "File ID not recognized"));

      if (body.mfa_required && body.mfa_token) {
        setMfaToken(body.mfa_token);
        setMfaMode(true);
        return;
      }

      await onSubmit?.(body, normalizedFileId);
    } catch (err) {
      const message = err?.message || "";
      if (message === "Failed to fetch" || err instanceof TypeError) {
        setError(
          "Cannot reach the server. Use http:// (not https://) and confirm the gateway is running.",
        );
      } else {
        setError(message || "File ID not recognized");
      }
    } finally {
      setLoading(false);
    }
  };

  const submitMfa = async () => {
    if (loading || !canSubmitMfa) return;
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${resolveApiBase()}/auth/mfa/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mfa_token: mfaToken, code: mfaCode.trim() }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(parseLoginError(body, "Invalid MFA code"));
      await onSubmit?.(body, normalizedFileId);
    } catch (err) {
      const message = err?.message || "";
      if (message === "Failed to fetch" || err instanceof TypeError) {
        setError(
          "Cannot reach the server. Use http:// (not https://) and confirm the gateway is running.",
        );
      } else {
        setError(message || "Invalid MFA code");
      }
    } finally {
      setLoading(false);
    }
  };

  if (mfaMode) {
    return (
      <div className="splash-login-inline" ref={formRef}>
        <h2 className="splash-login-inline__title">Sign in</h2>
        <p className="splash-login-inline__hint">Enter your authenticator code</p>
        <div className="splash-login-inline__row">
          <input
            id="splash-mfa-code"
            className={`splash-login-inline__input${error ? " splash-login-inline__input--error" : ""}`}
            value={mfaCode}
            onChange={(event) => setMfaCode(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") submitMfa();
            }}
            placeholder="6-digit code"
            inputMode="numeric"
            autoComplete="one-time-code"
            autoFocus
          />
          <button
            type="button"
            className="splash-login-inline__btn"
            disabled={!canSubmitMfa || loading}
            onClick={submitMfa}
          >
            {loading ? "…" : "→"}
          </button>
        </div>
        {error ? <p className="splash-login-inline__error">{error}</p> : null}
      </div>
    );
  }

  return (
    <div className="splash-login-inline" ref={formRef}>
      <h2 className="splash-login-inline__title">Sign in</h2>
      <div className="splash-login-inline__row">
        <input
          id="splash-file-id"
          className={`splash-login-inline__input${error ? " splash-login-inline__input--error" : ""}`}
          value={fileId}
          onChange={(event) => setFileId(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") submitLogin();
          }}
          placeholder="File ID e.g. 2721"
          autoComplete="off"
          inputMode="numeric"
          aria-label="File ID"
        />
        <button
          type="button"
          className="splash-login-inline__btn"
          disabled={!canSubmit || loading}
          onClick={submitLogin}
        >
          {loading ? "…" : "Sign In →"}
        </button>
      </div>
      {error ? <p className="splash-login-inline__error">{error}</p> : null}
    </div>
  );
}
