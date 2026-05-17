import { useEffect, useState } from "react";
import GlassCard from "../../components/glass/GlassCard";
import PageHeader from "../components/PageHeader";
import { adminApi } from "../api";

export default function Dashboard() {
  const [stats, setStats] = useState({ users: 0, roles: 0, flags: 0, queries: 0, costCents: 0 });
  const [events, setEvents] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const end = new Date();
        const start = new Date();
        start.setDate(end.getDate() - 29);
        const range = {
          date_from: start.toISOString().slice(0, 10),
          date_to: end.toISOString().slice(0, 10),
        };
        const [userList, rolesRes, flagsRes, auditRes, usageRes] = await Promise.all([
          adminApi.users({ limit: 200 }),
          adminApi.roles(),
          adminApi.featureFlags(),
          adminApi.audit({ limit: 8 }),
          adminApi.usage(range).catch(() => ({ summary: {} })),
        ]);
        if (cancelled) return;
        setStats({
          users: userList.users?.length ?? 0,
          roles: rolesRes.roles?.length ?? 0,
          flags: flagsRes.feature_flags?.length ?? 0,
          queries: usageRes.summary?.queries_count ?? 0,
          costCents: usageRes.summary?.cost_cents ?? 0,
        });
        setEvents(auditRes.events || []);
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <PageHeader title="Dashboard" subtitle="System overview and recent activity" />
      {error ? <div className="ooa-admin-error">{error}</div> : null}
      <div className="ooa-admin-stats">
        <GlassCard className="ooa-admin-stat">
          <div className="ooa-admin-stat-label">Users</div>
          <div className="ooa-admin-stat-value">{stats.users}</div>
        </GlassCard>
        <GlassCard className="ooa-admin-stat">
          <div className="ooa-admin-stat-label">Roles</div>
          <div className="ooa-admin-stat-value">{stats.roles}</div>
        </GlassCard>
        <GlassCard className="ooa-admin-stat">
          <div className="ooa-admin-stat-label">Feature flags</div>
          <div className="ooa-admin-stat-value">{stats.flags}</div>
        </GlassCard>
        <GlassCard className="ooa-admin-stat">
          <div className="ooa-admin-stat-label">Queries (30d)</div>
          <div className="ooa-admin-stat-value">{stats.queries}</div>
        </GlassCard>
        <GlassCard className="ooa-admin-stat">
          <div className="ooa-admin-stat-label">Est. cost (30d)</div>
          <div className="ooa-admin-stat-value">AED {(Number(stats.costCents) / 100).toFixed(2)}</div>
        </GlassCard>
      </div>
      <GlassCard style={{ padding: "1rem" }}>
        <h2 style={{ margin: "0 0 0.75rem", fontSize: "1rem" }}>Recent activity</h2>
        {events.length === 0 ? (
          <p style={{ color: "var(--ooa-text-muted)" }}>No audit events yet.</p>
        ) : (
          <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
            {events.map((e) => (
              <li key={e.id} style={{ padding: "0.45rem 0", borderBottom: "1px solid var(--ooa-glass-border)" }}>
                <span style={{ color: "var(--ooa-text-muted)", fontSize: "0.8rem" }}>
                  {e.created_at ? new Date(e.created_at).toLocaleString() : "—"}
                </span>
                {" · "}
                <strong>{e.event_action}</strong>
                {e.status ? ` (${e.status})` : ""}
              </li>
            ))}
          </ul>
        )}
      </GlassCard>
    </>
  );
}
