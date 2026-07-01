"use client";

import { useEffect, useMemo, useState } from "react";
import { API_BASE, getToken } from "@/lib/api";

type Competency = {
  key: string;
  category: string;
  description: string;
  is_legacy: boolean;
  sort_order: number;
};

type Coach = {
  code: string;
  name: string;
  email: string | null;
  phone: string | null;
  org: string | null;
  state: string | null;
  cert_status: number;
  cert_date: string | null;
  competencies: Record<string, boolean>;
};

const CERT_LABELS = ["Not Certified", "Certified"];

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  return { Authorization: `Bearer ${getToken() ?? ""}`, ...extra };
}

export default function TrackerPage() {
  const [coaches, setCoaches] = useState<Coach[]>([]);
  const [competencies, setCompetencies] = useState<Competency[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<Coach | null>(null);
  const [showAddCoach, setShowAddCoach] = useState(false);
  const [newCoach, setNewCoach] = useState({ code: "", name: "", email: "", org: "", state: "" });

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [coachesRes, compsRes] = await Promise.all([
        fetch(`${API_BASE}/api/tracker/coaches`, { headers: authHeaders() }),
        fetch(`${API_BASE}/api/tracker/competencies`, { headers: authHeaders() }),
      ]);
      if (!coachesRes.ok || !compsRes.ok) throw new Error("Failed to load tracker data.");
      setCoaches(await coachesRes.json());
      setCompetencies(await compsRes.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load tracker data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const categories = useMemo(() => {
    const active = competencies.filter((c) => !c.is_legacy);
    const groups = new Map<string, Competency[]>();
    for (const c of active) {
      if (!groups.has(c.category)) groups.set(c.category, []);
      groups.get(c.category)!.push(c);
    }
    return groups;
  }, [competencies]);

  function categoryPct(coach: Coach, category: string): number {
    const keys = (categories.get(category) ?? []).map((c) => c.key);
    if (keys.length === 0) return 0;
    const done = keys.filter((k) => coach.competencies[k]).length;
    return Math.round((done / keys.length) * 100);
  }

  function overallPct(coach: Coach): number {
    const active = competencies.filter((c) => !c.is_legacy);
    if (active.length === 0) return 0;
    const done = active.filter((c) => coach.competencies[c.key]).length;
    return Math.round((done / active.length) * 100);
  }

  const filtered = coaches.filter((c) =>
    !q || c.name.toLowerCase().includes(q.toLowerCase()) || c.code.includes(q)
  );

  async function toggleCompetency(coach: Coach, key: string) {
    const newValue = !coach.competencies[key];
    const res = await fetch(`${API_BASE}/api/tracker/coaches/${coach.code}/competencies/${key}`, {
      method: "PUT",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ completed: newValue }),
    });
    if (res.ok) {
      const updated = { ...coach, competencies: { ...coach.competencies, [key]: newValue } };
      setCoaches((prev) => prev.map((c) => (c.code === coach.code ? updated : c)));
      setSelected(updated);
    }
  }

  async function createCoach() {
    if (!newCoach.code || !newCoach.name) return;
    const res = await fetch(`${API_BASE}/api/tracker/coaches`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        code: newCoach.code, name: newCoach.name,
        email: newCoach.email || null, org: newCoach.org || null, state: newCoach.state || null,
      }),
    });
    if (res.ok) {
      setShowAddCoach(false);
      setNewCoach({ code: "", name: "", email: "", org: "", state: "" });
      load();
    } else {
      setError((await res.json()).detail ?? "Failed to create coach.");
    }
  }

  async function updateCertStatus(coach: Coach, status: number) {
    const res = await fetch(`${API_BASE}/api/tracker/coaches/${coach.code}`, {
      method: "PUT",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ cert_status: status }),
    });
    if (res.ok) {
      const updated = { ...coach, cert_status: status };
      setCoaches((prev) => prev.map((c) => (c.code === coach.code ? updated : c)));
      setSelected(updated);
    }
  }

  if (loading) return <p style={{ color: "var(--esb-muted)" }}>Loading tracker…</p>;

  return (
    <div>
      {error && (
        <div style={{ background: "#fdecea", border: "1px solid #ed3c0d", borderRadius: "4px", padding: "10px 16px", color: "#ed3c0d", marginBottom: "20px", fontSize: "14px" }}>
          {error}
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
        <input
          className="esb-input"
          placeholder="Search coach name or code…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ width: "280px" }}
        />
        <button className="btn-primary" onClick={() => setShowAddCoach(true)}>+ Add Coach</button>
      </div>

      {showAddCoach && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50 }}>
          <div className="esb-card" style={{ width: "440px" }}>
            <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "20px", fontWeight: 700, marginBottom: "16px" }}>Add Coach</h2>
            {["code", "name", "email", "org", "state"].map((field) => (
              <input
                key={field}
                className="esb-input"
                placeholder={field[0].toUpperCase() + field.slice(1)}
                style={{ marginBottom: "10px" }}
                value={(newCoach as Record<string, string>)[field]}
                onChange={(e) => setNewCoach({ ...newCoach, [field]: e.target.value })}
              />
            ))}
            <div style={{ display: "flex", gap: "10px", marginTop: "8px" }}>
              <button className="btn-primary" onClick={createCoach}>Create</button>
              <button onClick={() => setShowAddCoach(false)} style={{ background: "none", border: "2px solid var(--esb-border)", borderRadius: "4px", padding: "10px 20px", cursor: "pointer" }}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {selected ? (
        <div className="esb-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "20px" }}>
            <div>
              <button
                onClick={() => setSelected(null)}
                style={{ background: "none", border: "none", color: "var(--esb-primary)", cursor: "pointer", fontSize: "13px", marginBottom: "8px", padding: 0 }}
              >
                ← Back to all coaches
              </button>
              <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "22px", fontWeight: 700, margin: 0 }}>
                {selected.name} <span style={{ color: "var(--esb-muted)", fontWeight: 400 }}>({selected.code})</span>
              </h2>
              <p style={{ color: "var(--esb-muted)", fontSize: "14px", marginTop: "4px" }}>
                {selected.org || "—"} · {selected.state || "—"} · {selected.email || "no email"}
              </p>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: "28px", fontWeight: 700, color: "var(--esb-primary)" }}>{overallPct(selected)}%</div>
              <select
                className="esb-input"
                value={selected.cert_status}
                onChange={(e) => updateCertStatus(selected, Number(e.target.value))}
                style={{ marginTop: "6px", fontSize: "13px" }}
              >
                {CERT_LABELS.map((label, i) => (
                  <option key={i} value={i}>{label}</option>
                ))}
              </select>
            </div>
          </div>

          {Array.from(categories.entries()).map(([category, comps]) => (
            <div key={category} style={{ marginBottom: "24px" }}>
              <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, color: "var(--esb-dark)", marginBottom: "10px" }}>
                {category} — {categoryPct(selected, category)}%
              </h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "8px" }}>
                {comps.map((comp) => {
                  const done = !!selected.competencies[comp.key];
                  return (
                    <label
                      key={comp.key}
                      style={{
                        display: "flex", alignItems: "flex-start", gap: "8px", padding: "8px 10px",
                        background: done ? "#e8f5e9" : "var(--esb-light-bg)", borderRadius: "4px", cursor: "pointer",
                        fontSize: "13px", lineHeight: "1.4",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={done}
                        onChange={() => toggleCompetency(selected, comp.key)}
                        style={{ marginTop: "2px" }}
                      />
                      <span>
                        <strong>{comp.key}</strong> — {comp.description}
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="esb-card" style={{ padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "var(--esb-light-bg)", borderBottom: "2px solid var(--esb-border)" }}>
                {["Code", "Name", "Org", "State", "Cert Status", "Overall Progress"].map((h) => (
                  <th key={h} style={{ padding: "12px 16px", textAlign: "left", fontFamily: "var(--font-heading)", fontSize: "13px", fontWeight: 700, color: "var(--esb-dark)" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((coach, i) => (
                <tr
                  key={coach.code}
                  onClick={() => setSelected(coach)}
                  style={{ borderBottom: "1px solid var(--esb-border)", background: i % 2 === 0 ? "#fff" : "var(--esb-light-bg)", cursor: "pointer" }}
                >
                  <td style={{ padding: "12px 16px", fontSize: "14px", fontWeight: 600 }}>{coach.code}</td>
                  <td style={{ padding: "12px 16px", fontSize: "14px" }}>{coach.name}</td>
                  <td style={{ padding: "12px 16px", fontSize: "13px", color: "var(--esb-muted)" }}>{coach.org || "—"}</td>
                  <td style={{ padding: "12px 16px", fontSize: "13px", color: "var(--esb-muted)" }}>{coach.state || "—"}</td>
                  <td style={{ padding: "12px 16px", fontSize: "13px" }}>
                    <span style={{
                      background: coach.cert_status === 1 ? "#e8f5e9" : "#fdecea",
                      color: coach.cert_status === 1 ? "#1b5e20" : "#ed3c0d",
                      padding: "2px 8px", borderRadius: "4px", fontWeight: 600,
                    }}>
                      {CERT_LABELS[coach.cert_status] ?? "Unknown"}
                    </span>
                  </td>
                  <td style={{ padding: "12px 16px", fontSize: "13px", fontWeight: 700, color: "var(--esb-primary)" }}>
                    {overallPct(coach)}%
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
