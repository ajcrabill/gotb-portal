"use client";

import { useEffect, useState } from "react";

type ScoringConfig = {
  id: string;
  content_hash: string;
  is_active: boolean;
  config: {
    version?: string;
    total_ceiling?: number;
    practices?: Record<string, {
      ceiling: number;
      band_scores: number[];
    }>;
  };
  created_at: string;
};

export default function ScoringConfigPage() {
  const [configs, setConfigs] = useState<ScoringConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);

  function token() { return sessionStorage.getItem("esb_token") ?? ""; }

  useEffect(() => {
    fetch("/api/admin/scoring", { headers: { Authorization: `Bearer ${token()}` } })
      .then((r) => r.json())
      .then((data) => {
        setConfigs(data);
        const active = data.find((c: ScoringConfig) => c.is_active);
        if (active) setSelected(active.id);
      })
      .finally(() => setLoading(false));
  }, []);

  const activeConfig = configs.find((c) => c.id === selected);

  return (
    <div className="container mx-auto px-4 py-10">
      <div style={{ marginBottom: "28px" }}>
        <h1 style={{ fontFamily: "var(--font-heading)", fontSize: "28px", fontWeight: 700, margin: "0 0 4px" }}>
          Scoring Configuration
        </h1>
        <p style={{ color: "var(--esb-muted)", fontSize: "14px", margin: 0 }}>
          Append-only versioning. Each assessment session carries a FK to the exact config version it was scored against.
        </p>
      </div>

      {loading && <p style={{ color: "var(--esb-muted)" }}>Loading…</p>}

      {!loading && (
        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "24px" }}>
          {/* Version list */}
          <div>
            <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, marginBottom: "12px" }}>Versions</h2>
            {configs.map((c) => (
              <button
                key={c.id}
                onClick={() => setSelected(c.id)}
                style={{
                  display: "block", width: "100%", textAlign: "left",
                  padding: "12px 14px", marginBottom: "6px", borderRadius: "4px",
                  border: `2px solid ${c.id === selected ? "var(--esb-primary)" : "var(--esb-border)"}`,
                  background: c.id === selected ? "#f0f9ff" : "#fff", cursor: "pointer",
                }}
              >
                <div style={{ fontSize: "13px", fontWeight: 700, fontFamily: "var(--font-heading)", color: c.id === selected ? "var(--esb-primary)" : "var(--esb-dark)" }}>
                  {c.config.version ?? c.id.slice(0, 8)}
                  {c.is_active && <span style={{ marginLeft: "8px", background: "#28a745", color: "#fff", fontSize: "10px", padding: "1px 6px", borderRadius: "3px" }}>ACTIVE</span>}
                </div>
                <div style={{ fontSize: "12px", color: "var(--esb-muted)", marginTop: "2px" }}>
                  {new Date(c.created_at).toLocaleDateString()}
                </div>
                <div style={{ fontFamily: "monospace", fontSize: "11px", color: "var(--esb-muted)", marginTop: "2px" }}>
                  {c.content_hash.slice(0, 16)}…
                </div>
              </button>
            ))}
          </div>

          {/* Config detail */}
          {activeConfig && (
            <div className="esb-card">
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "20px" }}>
                <div>
                  <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "20px", fontWeight: 700, margin: "0 0 4px" }}>
                    {activeConfig.config.version ?? "Version " + activeConfig.id.slice(0, 8)}
                  </h2>
                  <p style={{ color: "var(--esb-muted)", fontSize: "13px", margin: 0 }}>
                    Hash: <code style={{ fontFamily: "monospace" }}>{activeConfig.content_hash}</code>
                  </p>
                </div>
                {activeConfig.config.total_ceiling && (
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: "36px", fontWeight: 700, fontFamily: "var(--font-heading)", color: "var(--esb-primary)", lineHeight: 1 }}>
                      {activeConfig.config.total_ceiling}
                    </div>
                    <div style={{ fontSize: "13px", color: "var(--esb-muted)" }}>Total ceiling</div>
                  </div>
                )}
              </div>

              {activeConfig.config.practices && (
                <div>
                  <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "15px", fontWeight: 700, marginBottom: "12px" }}>Practice Weights</h3>
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <thead>
                      <tr style={{ borderBottom: "2px solid var(--esb-border)", fontSize: "12px" }}>
                        <th style={{ padding: "8px 12px", textAlign: "left", fontWeight: 700 }}>Practice</th>
                        <th style={{ padding: "8px 12px", textAlign: "right", fontWeight: 700 }}>Max</th>
                        <th style={{ padding: "8px 12px", textAlign: "left", fontWeight: 700 }}>Band Scores (0→3)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(activeConfig.config.practices).map(([key, val]) => (
                        <tr key={key} style={{ borderBottom: "1px solid var(--esb-border)" }}>
                          <td style={{ padding: "10px 12px", fontWeight: 600, fontFamily: "var(--font-heading)", textTransform: "capitalize" }}>
                            {key.replace("_", " ")}
                          </td>
                          <td style={{ padding: "10px 12px", textAlign: "right", fontWeight: 700, color: "var(--esb-primary)" }}>
                            {val.ceiling}
                          </td>
                          <td style={{ padding: "10px 12px" }}>
                            <div style={{ display: "flex", gap: "8px" }}>
                              {val.band_scores.map((s, i) => (
                                <span key={i} style={{ background: "var(--esb-light-bg)", border: "1px solid var(--esb-border)", borderRadius: "4px", padding: "2px 10px", fontSize: "13px" }}>
                                  B{i}: {s}
                                </span>
                              ))}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <details style={{ marginTop: "20px" }}>
                <summary style={{ cursor: "pointer", fontSize: "13px", color: "var(--esb-muted)", fontWeight: 600 }}>Raw JSON</summary>
                <pre style={{ marginTop: "10px", padding: "12px", background: "#111", color: "#e0e0e0", borderRadius: "4px", fontSize: "12px", overflow: "auto", maxHeight: "400px" }}>
                  {JSON.stringify(activeConfig.config, null, 2)}
                </pre>
              </details>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
