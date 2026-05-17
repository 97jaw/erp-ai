import { useEffect, useState } from "react";
import GlassCard from "../../components/glass/GlassCard";
import PageHeader from "../components/PageHeader";
import { adminApi } from "../api";

export default function SecurityPage() {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    adminApi
      .securitySummary()
      .then(setSummary)
      .catch((err) => setError(err.message));
  }, []);

  return (
    <>
      <PageHeader title="Security" subtitle="Lockouts, MFA adoption, sessions, and recent failures" />
      {error ? <div className="ooa-admin-error">{error}</div> : null}
      {summary ? (
        <>
          <div className="ooa-admin-stats">
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">Locked accounts</div>
              <div className="ooa-admin-stat-value">{summary.locked_accounts}</div>
            </GlassCard>
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">MFA enabled</div>
              <div className="ooa-admin-stat-value">{summary.mfa_enabled_users}</div>
            </GlassCard>
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">Active sessions</div>
              <div className="ooa-admin-stat-value">{summary.active_sessions}</div>
            </GlassCard>
          </div>
          <GlassCard style={{ padding: "1rem" }}>
            <h2 style={{ margin: "0 0 0.5rem", fontSize: "1rem" }}>Rate limits</h2>
            <p style={{ margin: 0, color: "var(--ooa-text-muted)" }}>
              Login: {summary.rate_limits?.login_per_ip} · Admin: {summary.rate_limits?.admin_per_min}/min
            </p>
          </GlassCard>
          <GlassCard className="ooa-admin-table-wrap" style={{ marginTop: "1rem" }}>
            <h2 style={{ margin: "0 0 0.75rem", fontSize: "1rem" }}>Recent auth failures</h2>
            <table className="ooa-admin-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>User</th>
                  <th>Action</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {(summary.recent_auth_failures || []).map((e) => (
                  <tr key={e.id}>
                    <td>{e.created_at ? new Date(e.created_at).toLocaleString() : "—"}</td>
                    <td>{e.user_id ?? "—"}</td>
                    <td>{e.event_action}</td>
                    <td>{e.ip_address ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </GlassCard>
        </>
      ) : null}
    </>
  );
}
