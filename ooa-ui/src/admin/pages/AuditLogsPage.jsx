import { useEffect, useState } from "react";
import GlassCard from "../../components/glass/GlassCard";
import PageHeader from "../components/PageHeader";
import { adminApi } from "../api";

export default function AuditLogsPage() {
  const [events, setEvents] = useState([]);
  const [error, setError] = useState("");
  const [eventType, setEventType] = useState("");

  const load = () => {
    const params = { limit: 100 };
    if (eventType) params.event_type = eventType;
    adminApi
      .audit(params)
      .then((d) => setEvents(d.events || []))
      .catch((err) => setError(err.message));
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <>
      <PageHeader title="Audit logs" />
      {error ? <div className="ooa-admin-error">{error}</div> : null}
      <div className="ooa-admin-toolbar">
        <select className="ooa-glass-input" value={eventType} onChange={(e) => setEventType(e.target.value)}>
          <option value="">All types</option>
          <option value="auth">auth</option>
          <option value="admin">admin</option>
          <option value="security">security</option>
          <option value="query">query</option>
        </select>
        <button type="button" className="ooa-glass-button" onClick={load}>
          Filter
        </button>
        <button
          type="button"
          className="ooa-glass-button"
          onClick={() => adminApi.auditExport(eventType ? { event_type: eventType } : {}).catch((err) => setError(err.message))}
        >
          Export CSV
        </button>
      </div>
      <GlassCard className="ooa-admin-table-wrap">
        <table className="ooa-admin-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>User</th>
              <th>Type</th>
              <th>Action</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id}>
                <td>{e.created_at ? new Date(e.created_at).toLocaleString() : "—"}</td>
                <td>{e.user_id ?? "—"}</td>
                <td>{e.event_type}</td>
                <td>{e.event_action}</td>
                <td>{e.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </GlassCard>
    </>
  );
}
