"use client";

import { API_BASE } from "@/lib/api";
import { useEffect, useState } from "react";

type Scenario = {
  id: string;
  scenario_type: string;
  template_version: string;
  difficulty: string;
  is_active: boolean;
  focus_areas: string[];
  attempts: number;
  attempts_passed: number;
  avg_kappa: number | null;
  created_at: string;
};

type Stats = {
  total_scenarios: number;
  total_attempts: number;
  total_passed: number;
  overall_pass_rate: number | null;
  avg_kappa: number | null;
};

export default function AdminIrrScenariosPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function token() { return sessionStorage.getItem("esb_token") ?? ""; }

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [statsRes, scenariosRes] = await Promise.all([
        fetch(`${API_BASE}/api/irr/admin/scenarios/stats`, { headers: { Authorization: `Bearer ${token()}` } }),
        fetch(`${API_BASE}/api/irr/admin/scenarios?limit=100`, { headers: { Authorization: `Bearer ${token()}` } }),
      ]);
      if (!statsRes.ok || !scenariosRes.ok) throw new Error("Failed to load IRR scenario data.");
      setStats(await statsRes.json());
      setScenarios(await scenariosRes.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load IRR scenario data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-esb-blue-dark">IRR Scenarios</h1>
      <p className="text-sm text-esb-slate">
        Scenarios are generated procedurally (not template-managed) — this view shows what practitioners have
        generated and how attempts have scored, so drift or unusually easy/hard batches are visible.
      </p>

      {error && (
        <div style={{ background: "#fff5f5", border: "1px solid #ed3c0d", borderRadius: "4px", padding: "12px 16px", color: "#ed3c0d", fontSize: "14px" }}>
          {error}
        </div>
      )}

      {loading && <p className="text-sm text-esb-slate">Loading…</p>}

      {stats && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {[
            { label: "Scenarios Generated", value: stats.total_scenarios },
            { label: "Scored Attempts", value: stats.total_attempts },
            { label: "Passed", value: stats.total_passed },
            { label: "Pass Rate", value: stats.overall_pass_rate !== null ? `${(stats.overall_pass_rate * 100).toFixed(0)}%` : "—" },
            { label: "Avg κ (kappa)", value: stats.avg_kappa ?? "—" },
          ].map((s) => (
            <div key={s.label} className="esb-card" style={{ textAlign: "center", padding: "16px" }}>
              <div style={{ fontSize: "24px", fontWeight: 700, color: "var(--esb-primary)" }}>{s.value}</div>
              <div style={{ fontSize: "12px", color: "var(--esb-muted)", marginTop: "4px" }}>{s.label}</div>
            </div>
          ))}
        </div>
      )}

      <div className="esb-card" style={{ padding: 0, overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "var(--esb-light-bg)" }}>
              {["Created", "Type", "Version", "Difficulty", "Focus Areas", "Attempts", "Passed", "Avg κ", "Active"].map((h) => (
                <th key={h} style={{ padding: "10px 14px", textAlign: "left", fontSize: "12px", fontWeight: 700 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {scenarios.map((s) => (
              <tr key={s.id} style={{ borderTop: "1px solid var(--esb-border)" }}>
                <td style={{ padding: "10px 14px", fontSize: "13px" }}>{new Date(s.created_at).toLocaleString()}</td>
                <td style={{ padding: "10px 14px", fontSize: "13px" }}>{s.scenario_type}</td>
                <td style={{ padding: "10px 14px", fontSize: "13px" }}>{s.template_version}</td>
                <td style={{ padding: "10px 14px", fontSize: "13px" }}>{s.difficulty}</td>
                <td style={{ padding: "10px 14px", fontSize: "12px", color: "var(--esb-muted)" }}>{s.focus_areas.join(", ")}</td>
                <td style={{ padding: "10px 14px", fontSize: "13px" }}>{s.attempts}</td>
                <td style={{ padding: "10px 14px", fontSize: "13px" }}>{s.attempts_passed}</td>
                <td style={{ padding: "10px 14px", fontSize: "13px" }}>{s.avg_kappa ?? "—"}</td>
                <td style={{ padding: "10px 14px", fontSize: "13px" }}>{s.is_active ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && scenarios.length === 0 && (
          <p style={{ padding: "16px", color: "var(--esb-muted)", fontSize: "14px" }}>
            No scenarios generated yet — practitioners generate one each time they open the Time Use Evaluation IRR Simulator.
          </p>
        )}
      </div>
    </div>
  );
}
