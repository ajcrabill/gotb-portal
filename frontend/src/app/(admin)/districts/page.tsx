"use client";

import { useState } from "react";

type District = {
  id: string;
  name: string;
  state: string;
  nces_lea_id: string | null;
  is_cgcs_member: boolean;
};

export default function AdminDistrictsPage() {
  const [q, setQ] = useState("");
  const [state, setState] = useState("");
  const [results, setResults] = useState<District[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newState, setNewState] = useState("");
  const [newNces, setNewNces] = useState("");
  const [msg, setMsg] = useState("");
  const [cgcsLoading, setCgcsLoading] = useState("");

  function token() { return sessionStorage.getItem("esb_token") ?? ""; }

  async function search() {
    if (!q.trim()) return;
    setLoading(true);
    const params = new URLSearchParams({ q });
    if (state) params.set("state", state);
    const res = await fetch(`/api/districts/search?${params}`, { headers: { Authorization: `Bearer ${token()}` } });
    setResults(await res.json());
    setLoading(false);
  }

  async function createDistrict() {
    if (!newName || !newState) { setMsg("Name and state are required."); return; }
    const res = await fetch("/api/districts/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token()}` },
      body: JSON.stringify({ name: newName, state: newState, nces_lea_id: newNces || null }),
    });
    const data = await res.json();
    if (res.ok || res.status === 201) {
      setMsg(`Created: ${data.name} (${data.state})`);
      setNewName(""); setNewState(""); setNewNces("");
      setCreating(false);
      setResults((prev) => [data, ...prev.filter((d) => d.id !== data.id)]);
    } else {
      setMsg(data.detail ?? "Failed.");
    }
  }

  async function toggleCgcs(district: District) {
    setCgcsLoading(district.id);
    const res = await fetch(`/api/districts/${district.id}/cgcs?is_cgcs=${!district.is_cgcs_member}`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token()}` },
    });
    if (res.ok) {
      setResults((prev) => prev.map((d) => d.id === district.id ? { ...d, is_cgcs_member: !d.is_cgcs_member } : d));
      setMsg(`CGCS flag ${!district.is_cgcs_member ? "set" : "cleared"} for ${district.name}`);
    } else {
      const data = await res.json();
      setMsg(data.detail ?? "Failed.");
    }
    setCgcsLoading("");
  }

  return (
    <div className="container mx-auto px-4 py-10">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "28px" }}>
        <h1 style={{ fontFamily: "var(--font-heading)", fontSize: "28px", fontWeight: 700, margin: 0 }}>Districts</h1>
        <button className="btn-primary" onClick={() => setCreating(!creating)}>
          {creating ? "Cancel" : "+ Add District"}
        </button>
      </div>

      {msg && (
        <div style={{ background: "#e8f5e9", border: "1px solid #28a745", borderRadius: "4px", padding: "10px 16px", color: "#1b5e20", marginBottom: "20px", fontSize: "14px" }}>
          {msg}
        </div>
      )}

      {/* Create form */}
      {creating && (
        <div className="esb-card" style={{ marginBottom: "24px" }}>
          <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "18px", fontWeight: 700, marginBottom: "16px" }}>Add District</h2>
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: "12px", marginBottom: "16px" }}>
            <input className="esb-input" placeholder="District name" value={newName} onChange={(e) => setNewName(e.target.value)} />
            <input className="esb-input" placeholder="State (TX)" maxLength={2} value={newState} onChange={(e) => setNewState(e.target.value.toUpperCase())} />
            <input className="esb-input" placeholder="NCES LEA ID (optional)" value={newNces} onChange={(e) => setNewNces(e.target.value)} />
          </div>
          <button className="btn-primary" onClick={createDistrict}>Add District</button>
        </div>
      )}

      {/* Search */}
      <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
        <input className="esb-input" placeholder="Search by name…" value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()} style={{ flex: 1 }} />
        <input className="esb-input" placeholder="State" maxLength={2} value={state}
          onChange={(e) => setState(e.target.value.toUpperCase())} style={{ width: "80px" }} />
        <button className="btn-primary" onClick={search}>Search</button>
      </div>

      {loading && <p style={{ color: "var(--esb-muted)" }}>Searching…</p>}

      {results.length > 0 && (
        <div className="esb-card" style={{ padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "var(--esb-light-bg)", borderBottom: "2px solid var(--esb-border)" }}>
                {["Name", "State", "NCES LEA ID", "CGCS", "Actions"].map((h) => (
                  <th key={h} style={{ padding: "12px 16px", textAlign: "left", fontFamily: "var(--font-heading)", fontSize: "13px", fontWeight: 700 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {results.map((d, i) => (
                <tr key={d.id} style={{ borderBottom: "1px solid var(--esb-border)", background: i % 2 === 0 ? "#fff" : "var(--esb-light-bg)" }}>
                  <td style={{ padding: "12px 16px", fontWeight: 600, fontSize: "14px" }}>{d.name}</td>
                  <td style={{ padding: "12px 16px", color: "var(--esb-muted)" }}>{d.state}</td>
                  <td style={{ padding: "12px 16px", fontFamily: "monospace", fontSize: "13px", color: "var(--esb-muted)" }}>{d.nces_lea_id ?? "—"}</td>
                  <td style={{ padding: "12px 16px" }}>
                    {d.is_cgcs_member ? (
                      <span style={{ background: "#fce4ec", color: "#c62828", fontSize: "12px", fontWeight: 700, padding: "3px 8px", borderRadius: "4px" }}>CGCS</span>
                    ) : (
                      <span style={{ color: "var(--esb-muted)", fontSize: "13px" }}>—</span>
                    )}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    <button
                      onClick={() => toggleCgcs(d)}
                      disabled={cgcsLoading === d.id}
                      style={{
                        fontSize: "12px", padding: "4px 12px", borderRadius: "4px", cursor: "pointer",
                        border: `1px solid ${d.is_cgcs_member ? "#c62828" : "var(--esb-border)"}`,
                        background: "none", color: d.is_cgcs_member ? "#c62828" : "var(--esb-muted)",
                        opacity: cgcsLoading === d.id ? 0.6 : 1,
                      }}
                    >
                      {cgcsLoading === d.id ? "…" : d.is_cgcs_member ? "Clear CGCS" : "Set CGCS"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {results.length === 0 && !loading && q && (
        <div style={{ textAlign: "center", padding: "40px", color: "var(--esb-muted)" }}>No districts found for "{q}"</div>
      )}
    </div>
  );
}
