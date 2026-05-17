import { useEffect, useState } from "react";
import { adminApi } from "./api";

export default function AdminGate({ children }) {
  const [state, setState] = useState("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    adminApi
      .me()
      .then((me) => {
        const canAdmin =
          me.is_super_admin ||
          (me.permissions || []).some((p) => p.startsWith("admin."));
        setState(canAdmin ? "ok" : "denied");
      })
      .catch((err) => {
        setState("error");
        setMessage(err.message);
      });
  }, []);

  if (state === "loading") {
    return <p style={{ padding: "2rem" }}>Checking admin access…</p>;
  }
  if (state === "denied") {
    return (
      <div className="ooa-admin-error" style={{ margin: "2rem" }}>
        You do not have permission to access the admin panel. Required: an admin.* permission or super admin role.
      </div>
    );
  }
  if (state === "error") {
    return <div className="ooa-admin-error" style={{ margin: "2rem" }}>{message}</div>;
  }
  return children;
}
