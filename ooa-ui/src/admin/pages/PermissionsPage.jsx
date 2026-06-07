import { useCallback, useEffect, useState } from "react";
import GlassCard from "../../components/glass/GlassCard";
import PageHeader from "../components/PageHeader";
import { adminApi } from "../api";

export default function PermissionsPage() {
  const [permissions, setPermissions] = useState([]);
  const [error, setError] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState(null);
  const [canSync, setCanSync] = useState(false);

  const load = useCallback(async () => {
    setError("");
    const [catalog, me] = await Promise.all([
      adminApi.permissions(),
      adminApi.me().catch(() => null),
    ]);
    setPermissions(catalog.permissions || []);
    const perms = me?.permissions || [];
    setCanSync(
      Boolean(me?.is_super_admin) || perms.includes("admin.settings.manage"),
    );
  }, []);

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, [load]);

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    setError("");
    try {
      const result = await adminApi.syncPermissions();
      setSyncResult(result);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSyncing(false);
    }
  };

  const byCategory = permissions.reduce((acc, p) => {
    const c = p.category || "other";
    if (!acc[c]) acc[c] = [];
    acc[c].push(p);
    return acc;
  }, {});

  const odooCount = (byCategory.odoo || []).length;

  return (
    <>
      <PageHeader title="Permissions" subtitle="Catalog of RBAC codes used by chat & admin" />
      {error ? <div className="ooa-admin-error">{error}</div> : null}
      {syncResult ? (
        <div className="ooa-admin-success" style={{ marginBottom: "0.75rem" }}>
          Synced — {syncResult.permissions_total} permissions total; super_admin{" "}
          {syncResult.super_admin_grants} grants; admin {syncResult.admin_grants} grants.
        </div>
      ) : null}
      {odooCount === 0 ? (
        <div className="ooa-admin-warn" style={{ marginBottom: "0.75rem" }}>
          No <code>odoo</code> permissions in the database yet. Restart the API (runs migrations)
          or click Sync role grants below.
        </div>
      ) : null}
      {canSync ? (
        <p style={{ marginBottom: "0.75rem" }}>
          <button type="button" className="ooa-admin-btn" disabled={syncing} onClick={handleSync}>
            {syncing ? "Syncing…" : "Sync role grants (super_admin + admin)"}
          </button>
        </p>
      ) : null}
      <GlassCard style={{ padding: "1rem" }}>
        {Object.entries(byCategory)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([cat, perms]) => (
            <section key={cat} style={{ marginBottom: "1.25rem" }}>
              <h3 style={{ textTransform: "capitalize" }}>
                {cat} <span style={{ opacity: 0.6 }}>({perms.length})</span>
              </h3>
              <ul className="ooa-admin-perm-list">
                {perms.map((p) => (
                  <li key={p.id}>
                    <code>{p.code}</code> — {p.display_name}
                  </li>
                ))}
              </ul>
            </section>
          ))}
      </GlassCard>
    </>
  );
}
