import { useState } from "react";
import { useNavigate } from "react-router-dom";
import GlassCard from "../../components/glass/GlassCard";
import GlassInput from "../../components/glass/GlassInput";
import PageHeader, { PrimaryButton, SecondaryButton } from "../components/PageHeader";
import { adminApi } from "../api";

export default function UserCreate() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    file_id: "",
    name: "",
    email: "",
    language: "en",
    role_name: "user",
    department_code: "IT",
  });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const res = await adminApi.createUser(form);
      navigate(`/admin/users/${res.user_id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <PageHeader title="Add user" backTo="/admin/users" />
      {error ? <div className="ooa-admin-error">{error}</div> : null}
      <GlassCard style={{ padding: "1.25rem", maxWidth: 560 }}>
        <form onSubmit={submit} className="ooa-admin-form-grid">
          <div className="ooa-admin-field">
            <label>File ID</label>
            <GlassInput className="ooa-glass-input" value={form.file_id} onChange={set("file_id")} required />
          </div>
          <div className="ooa-admin-field">
            <label>Name</label>
            <GlassInput className="ooa-glass-input" value={form.name} onChange={set("name")} required />
          </div>
          <div className="ooa-admin-field">
            <label>Email</label>
            <GlassInput className="ooa-glass-input" type="email" value={form.email} onChange={set("email")} />
          </div>
          <div className="ooa-admin-field">
            <label>Role</label>
            <select className="ooa-glass-input" value={form.role_name} onChange={set("role_name")}>
              <option value="user">user</option>
              <option value="manager">manager</option>
              <option value="admin">admin</option>
              <option value="auditor">auditor</option>
              <option value="guest">guest</option>
            </select>
          </div>
          <div className="ooa-admin-field">
            <label>Department code</label>
            <GlassInput className="ooa-glass-input" value={form.department_code} onChange={set("department_code")} />
          </div>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "flex-end" }}>
            <PrimaryButton type="submit" disabled={saving}>
              {saving ? "Saving…" : "Create user"}
            </PrimaryButton>
            <SecondaryButton type="button" onClick={() => navigate("/admin/users")}>
              Cancel
            </SecondaryButton>
          </div>
        </form>
      </GlassCard>
    </>
  );
}
