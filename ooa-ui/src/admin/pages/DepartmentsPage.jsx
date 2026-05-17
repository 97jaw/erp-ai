import { useEffect, useState } from "react";
import GlassCard from "../../components/glass/GlassCard";
import GlassInput from "../../components/glass/GlassInput";
import PageHeader, { PrimaryButton } from "../components/PageHeader";
import { adminApi } from "../api";

export default function DepartmentsPage() {
  const [departments, setDepartments] = useState([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ code: "", name: "", name_arabic: "" });

  const load = () =>
    adminApi
      .departments()
      .then((d) => setDepartments(d.departments || []))
      .catch((err) => setError(err.message));

  useEffect(() => {
    load();
  }, []);

  const create = async (e) => {
    e.preventDefault();
    try {
      await adminApi.createDepartment({
        code: form.code.toUpperCase(),
        name: form.name,
        name_arabic: form.name_arabic || undefined,
      });
      setForm({ code: "", name: "", name_arabic: "" });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <>
      <PageHeader title="Departments" />
      {error ? <div className="ooa-admin-error">{error}</div> : null}
      <GlassCard style={{ padding: "1rem", marginBottom: "1rem" }}>
        <form onSubmit={create} className="ooa-admin-toolbar">
          <GlassInput className="ooa-glass-input" placeholder="Code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required />
          <GlassInput className="ooa-glass-input" placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          <PrimaryButton type="submit">Add department</PrimaryButton>
        </form>
      </GlassCard>
      <GlassCard className="ooa-admin-table-wrap">
        <table className="ooa-admin-table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Arabic</th>
            </tr>
          </thead>
          <tbody>
            {departments.map((d) => (
              <tr key={d.id}>
                <td>{d.code}</td>
                <td>{d.name}</td>
                <td>{d.name_arabic || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </GlassCard>
    </>
  );
}
