import { useCallback, useEffect, useState } from "react";
import GlassCard from "../../components/glass/GlassCard";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge";
import { adminApi } from "../api";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "ai", label: "AI operations" },
  { id: "api", label: "API health" },
  { id: "odoo", label: "Odoo" },
  { id: "infra", label: "Infrastructure" },
  { id: "users", label: "Users" },
  { id: "costs", label: "Costs" },
  { id: "logs", label: "Logs" },
  { id: "alerts", label: "Alerts" },
];

const PERIOD_TABS = new Set(["ai", "odoo", "users", "costs"]);

function centsUsd(cents) {
  if (cents == null || cents < 0) return "—";
  return `$${(Number(cents) / 100).toFixed(2)}`;
}

function formatCredits(prov) {
  if (!prov || prov.credits_remaining < 0) return "—";
  if (prov.unit === "characters") {
    return `${Math.round(prov.credits_remaining).toLocaleString()} chars`;
  }
  return centsUsd(prov.credits_remaining);
}

function AlertRow({ alert, onSilence }) {
  const [silencing, setSilencing] = useState(false);
  const name = alert.name;
  const handleSilence = async () => {
    if (!name || silencing) return;
    setSilencing(true);
    try {
      await adminApi.alertSilence({
        alertname: name,
        duration_hours: 2,
        comment: "Silenced from OOA admin monitoring",
      });
      onSilence?.();
    } catch (err) {
      window.alert(err.message || "Silence failed");
    } finally {
      setSilencing(false);
    }
  };
  return (
    <li style={{ padding: "0.5rem 0", borderBottom: "1px solid var(--ooa-glass-border)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", flexWrap: "wrap" }}>
        <div>
          <strong>{name}</strong> ({alert.state || alert.severity}) — {alert.summary}
        </div>
        {name ? (
          <button
            type="button"
            className="ooa-admin-btn-secondary"
            style={{ fontSize: "0.8rem", padding: "0.2rem 0.5rem" }}
            disabled={silencing}
            onClick={handleSilence}
          >
            {silencing ? "…" : "Silence 2h"}
          </button>
        ) : null}
      </div>
      {alert.runbook?.steps?.length ? (
        <ol style={{ margin: "0.35rem 0 0 1rem", fontSize: "0.85rem", color: "var(--ooa-text-muted)" }}>
          {alert.runbook.steps.slice(0, 3).map((step, j) => (
            <li key={j}>{step}</li>
          ))}
        </ol>
      ) : null}
    </li>
  );
}

function PeriodSelect({ days, onChange }) {
  return (
    <div className="ooa-admin-toolbar">
      <label>
        Period{" "}
        <select className="ooa-glass-input" value={days} onChange={(e) => onChange(Number(e.target.value))}>
          <option value={1}>24h</option>
          <option value={7}>7 days</option>
          <option value={30}>30 days</option>
        </select>
      </label>
    </div>
  );
}

function DailyBars({ daily, valueKey = "queries_count" }) {
  if (!daily?.length) return null;
  const max = Math.max(...daily.map((d) => Number(d[valueKey]) || 0), 1);
  return (
    <div className="ooa-admin-daily-bars" style={{ display: "flex", alignItems: "flex-end", gap: "4px", height: 64, marginTop: "0.75rem" }} role="img" aria-label="Daily trend">
      {daily.map((d) => {
        const v = Number(d[valueKey]) || 0;
        const h = Math.max(4, (v / max) * 100);
        return (
          <div
            key={d.date}
            title={`${d.date}: ${v}`}
            style={{
              flex: 1,
              height: `${h}%`,
              background: "var(--ooa-accent, #6366f1)",
              borderRadius: 2,
              opacity: 0.85,
            }}
          />
        );
      })}
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: "1rem",
        padding: "0.25rem 0",
        fontSize: "0.9rem",
      }}
    >
      <span style={{ color: "var(--ooa-text-muted)" }}>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function MonitoringPage() {
  const [tab, setTab] = useState("overview");
  const [days, setDays] = useState(7);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const payload = {};
      if (tab === "overview") payload.overview = await adminApi.metricsOverview({ days: 1 });
      if (tab === "ai") payload.ai = await adminApi.metricsAi({ days });
      if (tab === "api") payload.api = await adminApi.metricsApiHealth(false);
      if (tab === "odoo") payload.odoo = await adminApi.metricsOdoo({ days });
      if (tab === "infra") payload.infra = await adminApi.metricsInfrastructure();
      if (tab === "users") payload.users = await adminApi.metricsUsers({ days });
      if (tab === "costs") payload.costs = await adminApi.metricsCosts({ days });
      if (tab === "logs") payload.logs = await adminApi.metricsLogs({ limit: 80 });
      if (tab === "alerts") payload.alerts = await adminApi.metricsAlerts();
      setData((prev) => ({ ...prev, ...payload }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [tab, days]);

  useEffect(() => {
    load();
  }, [load]);

  const refreshApi = async () => {
    try {
      const api = await adminApi.metricsApiHealth(true);
      setData((prev) => ({ ...prev, api }));
    } catch (err) {
      setError(err.message);
    }
  };

  const { overview, ai, api, odoo, infra, users, costs, logs, alerts } = data;

  return (
    <>
      <PageHeader
        title="Monitoring"
        subtitle="Metrics, Odoo, users, costs, logs, and alerts — Grafana: localhost:3030"
        actions={
          <button type="button" className="ooa-glass-button" onClick={load} disabled={loading}>
            {loading ? "Loading…" : "Refresh"}
          </button>
        }
      />
      {error ? <div className="ooa-admin-error">{error}</div> : null}

      <div className="ooa-admin-tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            className={`ooa-admin-tab${tab === t.id ? " is-active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {PERIOD_TABS.has(tab) ? <PeriodSelect days={days} onChange={setDays} /> : null}

      {tab === "overview" && overview ? (
        <>
          {!overview.prometheus_ok ? (
            <div className="ooa-admin-warn">
              Prometheus unreachable: {overview.prometheus_error || "check OOA_PROMETHEUS_URL"}
            </div>
          ) : null}
          <div className="ooa-admin-stats">
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">Queries (24h DB)</div>
              <div className="ooa-admin-stat-value">{overview.usage?.queries_count ?? 0}</div>
            </GlassCard>
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">Est. cost (DB)</div>
              <div className="ooa-admin-stat-value">{centsUsd(overview.usage?.cost_cents)}</div>
            </GlassCard>
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">API providers up</div>
              <div className="ooa-admin-stat-value">
                {overview.api_providers_up}/{overview.api_providers_total}
              </div>
            </GlassCard>
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">Firing alerts</div>
              <div className="ooa-admin-stat-value">{overview.firing_alert_count ?? 0}</div>
            </GlassCard>
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">Gateway scrape</div>
              <div className="ooa-admin-stat-value">{overview.metrics?.gateway_up ? "UP" : "DOWN"}</div>
            </GlassCard>
          </div>
          {overview.firing_alerts?.length > 0 ? (
            <GlassCard style={{ padding: "1rem" }}>
              <h2 style={{ margin: "0 0 0.5rem", fontSize: "1rem" }}>Active alerts</h2>
              <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
                {overview.firing_alerts.map((a, i) => (
                  <li key={i} style={{ padding: "0.35rem 0" }}>
                    <span className="ooa-admin-badge ooa-admin-badge--warn">{a.severity || "alert"}</span>{" "}
                    {a.summary || a.name}
                  </li>
                ))}
              </ul>
            </GlassCard>
          ) : null}
        </>
      ) : null}

      {tab === "ai" && ai ? (
        <>
          <div className="ooa-admin-stats">
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">Input tokens</div>
              <div className="ooa-admin-stat-value">{Math.round(ai.prometheus?.input_tokens ?? 0)}</div>
            </GlassCard>
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">Output tokens</div>
              <div className="ooa-admin-stat-value">{Math.round(ai.prometheus?.output_tokens ?? 0)}</div>
            </GlassCard>
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">AI cost (Prometheus)</div>
              <div className="ooa-admin-stat-value">{centsUsd(ai.prometheus?.cost_cents)}</div>
            </GlassCard>
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">Queries (DB)</div>
              <div className="ooa-admin-stat-value">{ai.usage?.queries_count ?? 0}</div>
            </GlassCard>
          </div>
          {ai.usage?.daily?.length ? (
            <GlassCard style={{ padding: "1rem", marginBottom: "1rem" }}>
              <h2 style={{ margin: "0 0 0.25rem", fontSize: "1rem" }}>Daily queries (DB)</h2>
              <DailyBars daily={ai.usage.daily} valueKey="queries_count" />
            </GlassCard>
          ) : null}
          <GlassCard className="ooa-admin-table-wrap">
            <h2 style={{ margin: "0 0 0.75rem", fontSize: "1rem" }}>Top tools</h2>
            <table className="ooa-admin-table">
              <thead>
                <tr>
                  <th>Tool</th>
                  <th>Executions</th>
                </tr>
              </thead>
              <tbody>
                {(ai.prometheus?.tools || []).map((row) => (
                  <tr key={row.labels?.tool_name || String(row.value)}>
                    <td>{row.labels?.tool_name || "—"}</td>
                    <td>{Math.round(row.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </GlassCard>
        </>
      ) : null}

      {tab === "api" && api ? (
        <>
          <div className="ooa-admin-toolbar">
            <button type="button" className="ooa-glass-button" onClick={refreshApi}>
              Refresh provider checks
            </button>
          </div>
          {Object.entries(api.providers || {}).map(([name, prov]) => (
            <GlassCard key={name} style={{ padding: "1rem", marginBottom: "0.75rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0, textTransform: "capitalize" }}>{name}</h3>
                <StatusBadge active={!!prov.up} />
              </div>
              <Row label="Credits / quota" value={formatCredits(prov)} />
              {prov.detail ? (
                <p style={{ fontSize: "0.8rem", color: "var(--ooa-text-muted)", marginTop: "0.5rem" }}>
                  {prov.detail}
                </p>
              ) : null}
            </GlassCard>
          ))}
        </>
      ) : null}

      {tab === "odoo" && odoo ? (
        <>
          {!odoo.ok ? (
            <div className="ooa-admin-warn">{odoo.error || "Prometheus unavailable"}</div>
          ) : null}
          <div className="ooa-admin-stats">
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">Odoo p95 latency</div>
              <div className="ooa-admin-stat-value">
                {odoo.odoo_p95_seconds != null ? `${Number(odoo.odoo_p95_seconds).toFixed(2)}s` : "—"}
              </div>
            </GlassCard>
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">Tool p95 latency</div>
              <div className="ooa-admin-stat-value">
                {odoo.tool_p95_seconds != null ? `${Number(odoo.tool_p95_seconds).toFixed(2)}s` : "—"}
              </div>
            </GlassCard>
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">Odoo errors (period)</div>
              <div className="ooa-admin-stat-value">{Math.round(odoo.odoo_errors ?? 0)}</div>
            </GlassCard>
          </div>
          <GlassCard className="ooa-admin-table-wrap" style={{ marginBottom: "1rem" }}>
            <h2 style={{ margin: "0 0 0.75rem", fontSize: "1rem" }}>Odoo XML-RPC calls</h2>
            <table className="ooa-admin-table">
              <thead>
                <tr>
                  <th>Method</th>
                  <th>Status</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {(odoo.odoo_calls || []).length === 0 ? (
                  <tr>
                    <td colSpan={3}>No Odoo calls yet — run a chat query against Odoo.</td>
                  </tr>
                ) : (
                  (odoo.odoo_calls || []).map((row, i) => (
                    <tr key={i}>
                      <td>{row.labels?.method || "—"}</td>
                      <td>{row.labels?.status || "—"}</td>
                      <td>{Math.round(row.value)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </GlassCard>
          <GlassCard className="ooa-admin-table-wrap">
            <h2 style={{ margin: "0 0 0.75rem", fontSize: "1rem" }}>Top tools (same period)</h2>
            <table className="ooa-admin-table">
              <thead>
                <tr>
                  <th>Tool</th>
                  <th>Executions</th>
                </tr>
              </thead>
              <tbody>
                {(odoo.tool_executions || []).map((row, i) => (
                  <tr key={i}>
                    <td>{row.labels?.tool_name || "—"}</td>
                    <td>{Math.round(row.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </GlassCard>
        </>
      ) : null}

      {tab === "users" && users ? (
        <>
          <div className="ooa-admin-stats">
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">Active users</div>
              <div className="ooa-admin-stat-value">{users.summary?.active_users ?? 0}</div>
            </GlassCard>
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">Queries</div>
              <div className="ooa-admin-stat-value">{users.summary?.queries_count ?? 0}</div>
            </GlassCard>
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">Tokens</div>
              <div className="ooa-admin-stat-value">{users.summary?.tokens_used ?? 0}</div>
            </GlassCard>
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">Est. cost</div>
              <div className="ooa-admin-stat-value">{centsUsd(users.summary?.cost_cents)}</div>
            </GlassCard>
          </div>
          <GlassCard className="ooa-admin-table-wrap">
            <h2 style={{ margin: "0 0 0.75rem", fontSize: "1rem" }}>Top users by activity</h2>
            <table className="ooa-admin-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Queries</th>
                  <th>Tokens</th>
                  <th>Cost</th>
                </tr>
              </thead>
              <tbody>
                {(users.users || []).length === 0 ? (
                  <tr>
                    <td colSpan={4}>No usage recorded in this period.</td>
                  </tr>
                ) : (
                  (users.users || []).map((u) => (
                    <tr key={u.user_id || u.id}>
                      <td>{u.name || u.file_id || u.user_id}</td>
                      <td>{u.queries_count ?? 0}</td>
                      <td>{u.tokens_used ?? 0}</td>
                      <td>{centsUsd(u.cost_cents)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </GlassCard>
        </>
      ) : null}

      {tab === "costs" && costs ? (
        <>
          <div className="ooa-admin-stats">
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">Total cost (DB)</div>
              <div className="ooa-admin-stat-value">{centsUsd(costs.costs?.db?.cost_cents)}</div>
            </GlassCard>
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">AI cost (Prometheus)</div>
              <div className="ooa-admin-stat-value">{centsUsd(costs.costs?.prometheus?.total_ai_cents)}</div>
            </GlassCard>
            <GlassCard className="ooa-admin-stat">
              <div className="ooa-admin-stat-label">Anthropic (Prometheus)</div>
              <div className="ooa-admin-stat-value">{centsUsd(costs.costs?.prometheus?.anthropic_cents)}</div>
            </GlassCard>
          </div>
          <GlassCard className="ooa-admin-table-wrap" style={{ marginBottom: "1rem" }}>
            <h2 style={{ margin: "0 0 0.75rem", fontSize: "1rem" }}>Cost breakdown (DB)</h2>
            <table className="ooa-admin-table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(costs.costs?.db?.breakdown || {}).map(([k, v]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{typeof v === "number" ? centsUsd(v) : String(v)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </GlassCard>
          <GlassCard style={{ padding: "1rem" }}>
            <h2 style={{ margin: "0 0 0.5rem", fontSize: "1rem" }}>Provider balances</h2>
            {Object.entries(costs.costs?.providers || {}).map(([name, prov]) => (
              <Row key={name} label={name} value={formatCredits(prov)} />
            ))}
          </GlassCard>
        </>
      ) : null}

      {tab === "infra" && infra ? (
        <GlassCard className="ooa-admin-table-wrap">
          <h2 style={{ margin: "0 0 0.75rem", fontSize: "1rem" }}>Prometheus targets</h2>
          <table className="ooa-admin-table">
            <thead>
              <tr>
                <th>Job</th>
                <th>Health</th>
                <th>Last error</th>
              </tr>
            </thead>
            <tbody>
              {(infra.targets || []).map((t, i) => (
                <tr key={t.job || i}>
                  <td>{t.job || "—"}</td>
                  <td>{t.health === "up" ? "UP" : t.health || "—"}</td>
                  <td style={{ fontSize: "0.8rem" }}>{t.last_error || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </GlassCard>
      ) : null}

      {tab === "logs" && logs ? (
        <GlassCard className="ooa-admin-table-wrap">
          <p style={{ fontSize: "0.85rem", color: "var(--ooa-text-muted)" }}>
            Source: {logs.source}
            {logs.path ? ` · ${logs.path}` : ""} · {logs.count} entries
          </p>
          <div className="ooa-admin-log-viewer">
            {(logs.entries || []).map((entry, i) => (
              <pre key={i} className="ooa-admin-log-line">
                {entry.timestamp || entry.timestamp_ns || "—"} [{entry.level}] {entry.message}
                {entry.request_id ? ` · req=${entry.request_id}` : ""}
              </pre>
            ))}
          </div>
        </GlassCard>
      ) : null}

      {tab === "alerts" && alerts ? (
        <>
          {!alerts.notifications_configured ? (
            <GlassCard style={{ padding: "0.75rem 1rem", marginBottom: "1rem" }}>
              <p style={{ margin: 0, color: "var(--ooa-text-muted)", fontSize: "0.9rem" }}>
                Email/Slack notifications are off. Set ALERT_EMAIL_ENABLED or ALERT_SLACK_ENABLED in .env,
                run <code>python scripts/render_alertmanager_config.py</code>, then restart Alertmanager.
              </p>
            </GlassCard>
          ) : null}
          <GlassCard style={{ padding: "1rem", marginBottom: "1rem" }}>
            <h2 style={{ margin: "0 0 0.5rem", fontSize: "1rem" }}>Prometheus alerts</h2>
            {(alerts.prometheus || []).length === 0 ? (
              <p style={{ color: "var(--ooa-text-muted)" }}>No alerts from Prometheus.</p>
            ) : (
              <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
                {alerts.prometheus.map((a, i) => (
                  <AlertRow key={`p-${i}`} alert={a} onSilence={load} />
                ))}
              </ul>
            )}
          </GlassCard>
          <GlassCard style={{ padding: "1rem", marginBottom: "1rem" }}>
            <h2 style={{ margin: "0 0 0.5rem", fontSize: "1rem" }}>Alertmanager</h2>
            {(alerts.alertmanager || []).length === 0 ? (
              <p style={{ color: "var(--ooa-text-muted)" }}>No active Alertmanager alerts.</p>
            ) : (
              <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
                {alerts.alertmanager.map((a, i) => (
                  <AlertRow key={`am-${i}`} alert={a} onSilence={load} />
                ))}
              </ul>
            )}
          </GlassCard>
          {(alerts.runbooks || []).length > 0 ? (
            <GlassCard style={{ padding: "1rem" }}>
              <h2 style={{ margin: "0 0 0.75rem", fontSize: "1rem" }}>Runbooks</h2>
              <div className="ooa-admin-runbooks">
                {alerts.runbooks.map((rb) => (
                  <details key={rb.alertname} style={{ marginBottom: "0.5rem" }}>
                    <summary style={{ cursor: "pointer", fontWeight: 600 }}>
                      {rb.alertname} — {rb.title}
                    </summary>
                    <ol style={{ margin: "0.5rem 0 0 1.25rem", padding: 0 }}>
                      {(rb.steps || []).map((step, j) => (
                        <li key={j} style={{ marginBottom: "0.25rem" }}>
                          {step}
                        </li>
                      ))}
                    </ol>
                  </details>
                ))}
              </div>
            </GlassCard>
          ) : null}
        </>
      ) : null}
    </>
  );
}
