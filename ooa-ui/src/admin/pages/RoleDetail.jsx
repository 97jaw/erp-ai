import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import GlassCard from "../../components/glass/GlassCard";
import PageHeader from "../components/PageHeader";
import { adminApi } from "../api";

export default function RoleDetail() {
  const { id } = useParams();
  const [roleName, setRoleName] = useState("");
  const [assigned, setAssigned] = useState(new Set());
  const [allPerms, setAllPerms] = useState([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [rp, catalog] = await Promise.all([
        adminApi.rolePermissions(id),
        adminApi.permissions(),
      ]);
      setRoleName(rp.role_name);
      setAssigned(new Set((rp.permissions || []).map((p) => p.id)));
      setAllPerms(catalog.permissions || []);
    } catch (err) {
      setError(err.message);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const toggle = async (permId, has) => {
    try {
      if (has) await adminApi.revokeRolePermission(id, permId);
      else await adminApi.grantRolePermission(id, permId);
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  const byCategory = allPerms.reduce((acc, p) => {
    const c = p.category || "other";
    if (!acc[c]) acc[c] = [];
    acc[c].push(p);
    return acc;
  }, {});

  return (
    <>
      <PageHeader title={`Role: ${roleName}`} backTo="/admin/roles" />
      {error ? <div className="ooa-admin-error">{error}</div> : null}
      <GlassCard style={{ padding: "1rem" }}>
        {Object.entries(byCategory).map(([cat, perms]) => (
          <section key={cat} style={{ marginBottom: "1.25rem" }}>
            <h3 style={{ textTransform: "capitalize", marginBottom: "0.5rem" }}>{cat}</h3>
            {perms.map((p) => {
              const has = assigned.has(p.id);
              return (
                <label key={p.id} style={{ display: "block", marginBottom: "0.35rem", fontSize: "0.88rem" }}>
                  <input type="checkbox" checked={has} onChange={() => toggle(p.id, has)} /> {p.code} — {p.display_name}
                </label>
              );
            })}
          </section>
        ))}
      </GlassCard>
    </>
  );
}
