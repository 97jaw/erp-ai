import { useEffect, useState } from "react";
import GlassCard from "../../components/glass/GlassCard";
import PageHeader from "../components/PageHeader";
import { adminApi } from "../api";

function centsToAed(cents) {
  if (cents == null) return "—";
  return `AED ${(Number(cents) / 100).toFixed(2)}`;
}

export default function UsagePage() {
  const [summary, setSummary] = useState(null);
  const [costs, setCosts] = useState(null);
  const [byUser, setByUser] = useState([]);
  const [byDept, setByDept] = useState([]);
  const [daily, setDaily] = useState([]);
  const [error, setError] = useState("");
  const [days, setDays] = useState(30);

  const load = async () => {
    setError("");
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - (Number(days) - 1));
    const date_from = start.toISOString().slice(0, 10);
    const date_to = end.toISOString().slice(0, 10);
    const params = { date_from, date_to };
    try {
      const [usageRes, costsRes, usersRes, deptRes] = await Promise.all([
        adminApi.usage(params),
        adminApi.usageCosts(params),
        adminApi.usageByUser({ ...params, limit: 15 }),
        adminApi.usageByDepartment(params),
      ]);
      setSummary(usageRes.summary || {});
      setDaily(usageRes.daily || []);
      setCosts(costsRes.costs || {});
      setByUser(usersRes.users || []);
      setByDept(deptRes.departments || []);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    load();
  }, [days]);

  return (
    <>
      <PageHeader title="Usage & costs" subtitle="Queries, tokens, PDFs, and estimated spend" />
      {error ? <div className="ooa-admin-error">{error}</div> : null}
      <div className="ooa-admin-toolbar">
        <label>
          Period{" "}
          <select className="ooa-glass-input" value={days} onChange={(e) => setDays(e.target.value)}>
            <option value="7">7 days</option>
            <option value="30">30 days</option>
            <option value="90">90 days</option>
          </select>
        </label>
        <button type="button" className="ooa-glass-button" onClick={load}>
          Refresh
        </button>
      </div>
      <div className="ooa-admin-stats">
        <GlassCard className="ooa-admin-stat">
          <div className="ooa-admin-stat-label">Queries</div>
          <div className="ooa-admin-stat-value">{summary?.queries_count ?? 0}</div>
        </GlassCard>
        <GlassCard className="ooa-admin-stat">
          <div className="ooa-admin-stat-label">Tokens</div>
          <div className="ooa-admin-stat-value">{summary?.tokens_used ?? 0}</div>
        </GlassCard>
        <GlassCard className="ooa-admin-stat">
          <div className="ooa-admin-stat-label">PDFs</div>
          <div className="ooa-admin-stat-value">{summary?.pdfs_generated ?? 0}</div>
        </GlassCard>
        <GlassCard className="ooa-admin-stat">
          <div className="ooa-admin-stat-label">Est. cost</div>
          <div className="ooa-admin-stat-value">{centsToAed(costs?.total_cents ?? summary?.cost_cents)}</div>
        </GlassCard>
      </div>
      <div className="ooa-admin-two-col">
        <GlassCard className="ooa-admin-table-wrap">
          <h2 style={{ margin: "0 0 0.75rem", fontSize: "1rem" }}>Top users</h2>
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
              {byUser.map((u) => (
                <tr key={u.user_id}>
                  <td>{u.name || u.file_id || u.user_id}</td>
                  <td>{u.queries_count}</td>
                  <td>{u.tokens_used}</td>
                  <td>{centsToAed(u.cost_cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </GlassCard>
        <GlassCard className="ooa-admin-table-wrap">
          <h2 style={{ margin: "0 0 0.75rem", fontSize: "1rem" }}>By department</h2>
          <table className="ooa-admin-table">
            <thead>
              <tr>
                <th>Department</th>
                <th>Queries</th>
                <th>Users</th>
                <th>Cost</th>
              </tr>
            </thead>
            <tbody>
              {byDept.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ color: "var(--ooa-text-muted)" }}>
                    No department usage in this period.
                  </td>
                </tr>
              ) : (
                byDept.map((d) => (
                  <tr key={d.code}>
                    <td>{d.name}</td>
                    <td>{d.queries_count}</td>
                    <td>{d.active_users}</td>
                    <td>{centsToAed(d.cost_cents)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </GlassCard>
      </div>
      <GlassCard style={{ padding: "1rem", marginTop: "1rem" }}>
        <h2 style={{ margin: "0 0 0.75rem", fontSize: "1rem" }}>Daily activity</h2>
        {daily.length === 0 ? (
          <p style={{ color: "var(--ooa-text-muted)" }}>No usage recorded yet.</p>
        ) : (
          <table className="ooa-admin-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Queries</th>
                <th>Tokens</th>
                <th>Active users</th>
                <th>Cost</th>
              </tr>
            </thead>
            <tbody>
              {daily.map((row) => (
                <tr key={row.date}>
                  <td>{row.date}</td>
                  <td>{row.queries_count}</td>
                  <td>{row.tokens_used}</td>
                  <td>{row.active_users}</td>
                  <td>{centsToAed(row.cost_cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </GlassCard>
    </>
  );
}
