"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

type Person = {
  id: string;
  email: string;
  name: string;
  roles: string[];
  created_at: string;
};

const ALL_ROLES = [
  "client", "investor", "practitioner_in_training",
  "certified_practitioner", "senior_practitioner", "practitioner_manager",
  "business_manager", "content_manager", "lead_senior_practitioner", "superuser",
];

export default function AdminPeoplePage() {
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [grantTarget, setGrantTarget] = useState<Person | null>(null);
  const [selectedRole, setSelectedRole] = useState("");
  const [actionMsg, setActionMsg] = useState("");

  function token() { return sessionStorage.getItem("esb_token") ?? ""; }

  async function load(query = "") {
    setLoading(true);
    const params = query ? `?q=${encodeURIComponent(query)}` : "";
    const res = await fetch(`${API_BASE}/api/admin/people${params}`, {
      headers: { Authorization: `Bearer ${token()}` },
    });
    setPeople(await res.json());
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function grantRole() {
    if (!grantTarget || !selectedRole) return;
    const res = await fetch(`${API_BASE}/api/admin/people/roles`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token()}` },
      body: JSON.stringify({ person_id: grantTarget.id, role: selectedRole }),
    });
    if (res.ok) {
      setActionMsg(`Granted ${selectedRole} to ${grantTarget.email}`);
      setGrantTarget(null);
      setSelectedRole("");
      load();
    } else {
      setActionMsg((await res.json()).detail ?? "Failed.");
    }
  }

  async function revokeRole(person: Person, role: string) {
    const res = await fetch(`${API_BASE}/api/admin/people/${person.id}/roles/${role}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token()}` },
    });
    if (res.ok || res.status === 204) {
      setActionMsg(`Revoked ${role} from ${person.email}`);
      load();
    }
  }

  return (
    <div className="container mx-auto px-4 py-10">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "28px" }}>
        <h1 style={{ fontFamily: "var(--font-heading)", fontSize: "28px", fontWeight: 700, margin: 0 }}>People</h1>
        <div style={{ display: "flex", gap: "10px" }}>
          <input
            className="esb-input"
            placeholder="Search name or email…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load(q)}
            style={{ width: "240px" }}
          />
          <button className="btn-primary" onClick={() => load(q)}>Search</button>
        </div>
      </div>

      {actionMsg && (
        <div style={{ background: "#e8f5e9", border: "1px solid #28a745", borderRadius: "4px", padding: "10px 16px", color: "#1b5e20", marginBottom: "20px", fontSize: "14px" }}>
          {actionMsg}
        </div>
      )}

      {/* Grant role modal */}
      {grantTarget && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50 }}>
          <div className="esb-card" style={{ width: "420px" }}>
            <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "20px", fontWeight: 700, marginBottom: "16px" }}>
              Grant Role to {grantTarget.email}
            </h2>
            <select
              className="esb-input"
              style={{ marginBottom: "16px" }}
              value={selectedRole}
              onChange={(e) => setSelectedRole(e.target.value)}
            >
              <option value="">Select role…</option>
              {ALL_ROLES.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <div style={{ display: "flex", gap: "10px" }}>
              <button className="btn-primary" onClick={grantRole}>Grant</button>
              <button onClick={() => { setGrantTarget(null); setSelectedRole(""); }} style={{ background: "none", border: "2px solid var(--esb-border)", borderRadius: "4px", padding: "10px 20px", cursor: "pointer" }}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <p style={{ color: "var(--esb-muted)" }}>Loading…</p>
      ) : (
        <div className="esb-card" style={{ padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "var(--esb-light-bg)", borderBottom: "2px solid var(--esb-border)" }}>
                {["Name", "Email", "Roles", "Joined", "Actions"].map((h) => (
                  <th key={h} style={{ padding: "12px 16px", textAlign: "left", fontFamily: "var(--font-heading)", fontSize: "13px", fontWeight: 700, color: "var(--esb-dark)" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {people.map((p, i) => (
                <tr key={p.id} style={{ borderBottom: "1px solid var(--esb-border)", background: i % 2 === 0 ? "#fff" : "var(--esb-light-bg)" }}>
                  <td style={{ padding: "12px 16px", fontWeight: 600, fontSize: "14px" }}>{p.name || "—"}</td>
                  <td style={{ padding: "12px 16px", fontSize: "14px", color: "var(--esb-muted)" }}>{p.email}</td>
                  <td style={{ padding: "12px 16px" }}>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                      {p.roles.length === 0 && <span style={{ color: "var(--esb-muted)", fontSize: "13px" }}>No roles</span>}
                      {p.roles.map((r) => (
                        <span key={r} style={{ display: "inline-flex", alignItems: "center", gap: "4px", background: "#e3f2fd", color: "#1565c0", fontSize: "12px", fontWeight: 600, padding: "2px 8px", borderRadius: "4px" }}>
                          {r}
                          <button
                            onClick={() => revokeRole(p, r)}
                            title={`Revoke ${r}`}
                            style={{ background: "none", border: "none", cursor: "pointer", color: "#1565c0", lineHeight: 1, padding: 0, fontSize: "14px" }}
                          >×</button>
                        </span>
                      ))}
                    </div>
                  </td>
                  <td style={{ padding: "12px 16px", fontSize: "13px", color: "var(--esb-muted)" }}>
                    {p.created_at ? new Date(p.created_at).toLocaleDateString() : "—"}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <button
                      className="btn-outline"
                      onClick={() => setGrantTarget(p)}
                      style={{ fontSize: "13px", padding: "5px 12px" }}
                    >
                      + Role
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
