"use client";

import { API_BASE } from "@/lib/api";

import { useEffect, useState } from "react";

type AuditEntry = {
  id: string;
  actor_id: string | null;
  actor_role: string | null;
  actor_ip: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  payload_hash: string | null;
  pipeline_verdict: string | null;
  entry_hash: string;
  prev_hash: string | null;
  occurred_at: string;
};

export default function AuditLogPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  function token() { return sessionStorage.getItem("esb_token") ?? ""; }

  async function load() {
    setLoading(true);
    const params = new URLSearchParams({ limit: "200" });
    if (actionFilter) params.set("action_prefix", actionFilter);
    if (typeFilter)   params.set("resource_type", typeFilter);
    const res = await fetch(`${API_BASE}/api/admin/audit?${params}`, {
      headers: { Authorization: `Bearer ${token()}` },
    });
    setEntries(await res.json());
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="container mx-auto px-4 py-10">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "28px" }}>
        <div>
          <h1 style={{ fontFamily: "var(--font-heading)", fontSize: "28px", fontWeight: 700, margin: "0 0 4px" }}>
            Audit Log
          </h1>
          <p style={{ color: "var(--esb-muted)", fontSize: "14px", margin: 0 }}>WORM — hash-chained, append-only</p>
        </div>
        <div style={{ display: "flex", gap: "10px" }}>
          <input className="esb-input" placeholder="Action prefix…" value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
            style={{ width: "180px" }} />
          <input className="esb-input" placeholder="Resource type…" value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
            style={{ width: "180px" }} />
          <button className="btn-primary" onClick={load}>Filter</button>
        </div>
      </div>

      {loading ? (
        <p style={{ color: "var(--esb-muted)" }}>Loading…</p>
      ) : (
        <div className="esb-card" style={{ padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
            <thead>
              <tr style={{ background: "var(--esb-light-bg)", borderBottom: "2px solid var(--esb-border)" }}>
                {["When", "Action", "Resource", "Actor", "IP", "Hash"].map((h) => (
                  <th key={h} style={{ padding: "10px 14px", textAlign: "left", fontFamily: "var(--font-heading)", fontSize: "12px", fontWeight: 700, color: "var(--esb-dark)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map((e, i) => (
                <>
                  <tr
                    key={e.id}
                    style={{ borderBottom: "1px solid var(--esb-border)", background: i % 2 === 0 ? "#fff" : "var(--esb-light-bg)", cursor: "pointer" }}
                    onClick={() => setExpanded(expanded === e.id ? null : e.id)}
                  >
                    <td style={{ padding: "10px 14px", whiteSpace: "nowrap", color: "var(--esb-muted)" }}>
                      {new Date(e.occurred_at).toLocaleString()}
                    </td>
                    <td style={{ padding: "10px 14px", fontWeight: 600 }}>
                      <span style={{ color: e.action.startsWith("admin.") ? "#9c27b0" : "var(--esb-dark)" }}>
                        {e.action}
                      </span>
                    </td>
                    <td style={{ padding: "10px 14px" }}>
                      <span style={{ color: "var(--esb-muted)" }}>{e.resource_type}</span>
                      {e.resource_id && <span style={{ marginLeft: "6px", color: "var(--esb-primary)", fontFamily: "monospace" }}>{e.resource_id.split("-")[0]}…</span>}
                    </td>
                    <td style={{ padding: "10px 14px", fontFamily: "monospace", fontSize: "12px", color: "var(--esb-muted)" }}>
                      {e.actor_id ? e.actor_id.split("-")[0] + "…" : "system"}
                      {e.actor_role && <span style={{ marginLeft: "6px", color: "var(--esb-primary)" }}>({e.actor_role})</span>}
                    </td>
                    <td style={{ padding: "10px 14px", fontFamily: "monospace", fontSize: "12px", color: "var(--esb-muted)" }}>
                      {e.actor_ip ?? "—"}
                    </td>
                    <td style={{ padding: "10px 14px", fontFamily: "monospace", fontSize: "11px", color: "var(--esb-muted)" }}>
                      {e.entry_hash.slice(0, 12)}…
                    </td>
                  </tr>
                  {expanded === e.id && (
                    <tr key={`${e.id}-detail`} style={{ background: "#f8f9fa" }}>
                      <td colSpan={6} style={{ padding: "14px 16px" }}>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", fontSize: "13px" }}>
                          <div><strong>Entry hash:</strong> <code style={{ fontFamily: "monospace", fontSize: "12px" }}>{e.entry_hash}</code></div>
                          <div><strong>Prev hash:</strong> <code style={{ fontFamily: "monospace", fontSize: "12px" }}>{e.prev_hash ?? "genesis"}</code></div>
                          {e.payload_hash && <div><strong>Payload hash:</strong> <code style={{ fontFamily: "monospace", fontSize: "12px" }}>{e.payload_hash}</code></div>}
                          {e.pipeline_verdict && (
                            <div>
                              <strong>Pipeline verdict:</strong>
                              <span style={{ marginLeft: "8px", color: e.pipeline_verdict === "allow" ? "#28a745" : "#dc3545", fontWeight: 700 }}>
                                {e.pipeline_verdict}
                              </span>
                            </div>
                          )}
                          <div><strong>Full resource ID:</strong> <code>{e.resource_id ?? "—"}</code></div>
                          <div><strong>Full actor ID:</strong> <code>{e.actor_id ?? "—"}</code></div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
