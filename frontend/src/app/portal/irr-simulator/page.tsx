"use client";

/**
 * IRR Simulator — M20
 *
 * Three stages:
 *   1. Landing / progress overview
 *   2. Scoring — practitioner scores each rubric item for the generated scenario
 *   3. Results — kappa, per-item feedback, system vs. practitioner comparison
 */
import { useState, useEffect } from "react";
import { auth as apiAuth, API_BASE } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

type Stage = "landing" | "scoring" | "results";

type AgendaItem = {
  title: string;
  category: string;
  allocated_minutes: number;
};

type ScenarioData = {
  district: string;
  meeting_date: string;
  meeting_type: string;
  quorum_present: number;
  board_size: number;
  total_minutes: number;
  agenda_items: AgendaItem[];
  notes: string;
};

type ScenarioOut = {
  scenario_id: string;
  scenario_data: ScenarioData;
  item_count: number;
};

type AttemptResult = {
  attempt_id: string;
  kappa: number;
  passed: boolean;
  item_kappas: Record<string, number>;
  item_feedback: Record<string, string>;
  system_scores: Record<string, { score: number; pct_of_meeting: number; minutes: number; rationale: string }>;
  kappa_threshold: number;
  message: string;
};

type Progress = {
  attempts_total: number;
  attempts_passed: number;
  rolling_kappa: number | null;
  certified_at: string | null;
};

// ── Rubric items (mirrors backend TIME_USE_ITEMS) ─────────────────────────────

const RUBRIC_ITEMS = [
  {
    id: "student_outcomes",
    label: "Student Outcomes Focus",
    description: "Time spent directly on student achievement, outcome data, and goal review.",
    max_score: 4,
    options: [
      { score: 0, label: "No time on student outcomes" },
      { score: 1, label: "Minimal (<10%) — largely procedural" },
      { score: 2, label: "Some focus (10-25%) — discussed but not deeply analyzed" },
      { score: 3, label: "Significant (25-50%) — data reviewed and discussed" },
      { score: 4, label: "Primary focus (>50%) — deep analysis with goal connection" },
    ],
  },
  {
    id: "policy_governance",
    label: "Policy and Governance",
    description: "Time spent on policy adoption, revision, or governance matters.",
    max_score: 4,
    options: [
      { score: 0, label: "No policy/governance work" },
      { score: 1, label: "Perfunctory — rubber-stamp only" },
      { score: 2, label: "Some deliberation on policy items" },
      { score: 3, label: "Meaningful policy work with board discussion" },
      { score: 4, label: "Rigorous policy work with clear rationale and outcome connection" },
    ],
  },
  {
    id: "superintendent_evaluation",
    label: "Superintendent Direction / Evaluation",
    description: "Time spent on superintendent performance, direction-setting, or contract.",
    max_score: 4,
    options: [
      { score: 0, label: "No superintendent-facing work" },
      { score: 1, label: "Mentioned but no substantive discussion" },
      { score: 2, label: "Some discussion; lacks criteria or clear expectations" },
      { score: 3, label: "Substantive discussion with clear expectations" },
      { score: 4, label: "Rigorous evaluation with data-driven criteria and documented follow-through" },
    ],
  },
  {
    id: "community_engagement",
    label: "Community Engagement",
    description: "Time spent on genuine community input — not just public comment periods.",
    max_score: 4,
    options: [
      { score: 0, label: "No community engagement" },
      { score: 1, label: "Perfunctory public comment only" },
      { score: 2, label: "Some engagement; limited two-way exchange" },
      { score: 3, label: "Meaningful input sought and acknowledged" },
      { score: 4, label: "Structured, substantive engagement with documented impact on decisions" },
    ],
  },
  {
    id: "operational_minutiae",
    label: "Operational Minutiae (lower is better)",
    description: "Time spent on operational details that should be delegated to staff.",
    max_score: 4,
    inverse: true,
    options: [
      { score: 0, label: "Board appropriately delegated; no operational minutiae" },
      { score: 1, label: "Minimal (<5%) — isolated slippage" },
      { score: 2, label: "Moderate (5-15%) — noticeable scope creep" },
      { score: 3, label: "Significant (15-30%) — board frequently in staff territory" },
      { score: 4, label: "Dominant (>30%) — board acting as staff" },
    ],
  },
];

// ── API helpers ───────────────────────────────────────────────────────────────

function getToken() {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem("esb_token");
}

async function apiRequest<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts.headers as Record<string, string> | undefined),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.detail?.message ?? err?.detail ?? res.statusText);
  }
  return res.json();
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function IRRSimulatorPage() {
  const [stage, setStage] = useState<Stage>("landing");
  const [scenario, setScenario] = useState<ScenarioOut | null>(null);
  const [scores, setScores] = useState<Record<string, number>>({});
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest<Progress>("/api/irr/progress").then(setProgress).catch(() => {});
  }, []);

  async function handleGenerateScenario() {
    setLoading(true);
    setError("");
    try {
      const s = await apiRequest<ScenarioOut>("/api/irr/scenarios/generate", { method: "POST" });
      setScenario(s);
      setScores({});
      setResult(null);
      setStage("scoring");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to generate scenario.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit() {
    if (!scenario) return;
    const missing = RUBRIC_ITEMS.filter((item) => scores[item.id] === undefined);
    if (missing.length > 0) {
      setError(`Please score all items before submitting. Missing: ${missing.map((m) => m.label).join(", ")}`);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const practitioner_scores = Object.fromEntries(
        Object.entries(scores).map(([id, score]) => [id, { score }])
      );
      const r = await apiRequest<AttemptResult>("/api/irr/attempts", {
        method: "POST",
        body: JSON.stringify({ scenario_id: scenario.scenario_id, practitioner_scores }),
      });
      setResult(r);
      setProgress((prev) => ({
        attempts_total: (prev?.attempts_total ?? 0) + 1,
        attempts_passed: (prev?.attempts_passed ?? 0) + (r.passed ? 1 : 0),
        rolling_kappa: r.kappa,
        certified_at: prev?.certified_at ?? null,
      }));
      setStage("results");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to submit attempt.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      {/* Page header strip */}
      <div style={{ background: "var(--esb-section-dark)", padding: "40px 0 30px", color: "#fff" }}>
        <div className="container mx-auto px-4">
          <h1 style={{ fontFamily: "var(--font-heading)", fontSize: "34px", fontWeight: 700, color: "#fff", margin: 0 }}>
            IRR Simulator
          </h1>
          <p style={{ color: "#aaaaaa", marginTop: "8px", marginBottom: 0 }}>
            Practice inter-rater reliability on dynamically generated board meeting scenarios
          </p>
        </div>
      </div>

      <div className="container mx-auto px-4 py-10">

        {/* Progress bar */}
        {progress && (
          <div className="esb-card" style={{ marginBottom: "32px" }}>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <Stat label="Total Attempts" value={String(progress.attempts_total)} />
              <Stat label="Passed" value={String(progress.attempts_passed)} />
              <Stat
                label="Rolling κ"
                value={progress.rolling_kappa !== null ? progress.rolling_kappa.toFixed(3) : "—"}
                color={progress.rolling_kappa !== null && progress.rolling_kappa >= 0.70 ? "#18d26e" : "var(--esb-primary)"}
              />
              <Stat
                label="IRR Certified"
                value={progress.certified_at ? "Yes ✓" : "Not yet"}
                color={progress.certified_at ? "#18d26e" : "var(--esb-muted)"}
              />
            </div>
          </div>
        )}

        {error && (
          <div
            style={{
              background: "#fff5f5",
              border: "1px solid #ed3c0d",
              borderRadius: "4px",
              padding: "12px 16px",
              color: "#ed3c0d",
              marginBottom: "24px",
              fontSize: "14px",
            }}
          >
            {error}
          </div>
        )}

        {/* Landing stage */}
        {stage === "landing" && (
          <div className="esb-card" style={{ maxWidth: "700px", margin: "0 auto", textAlign: "center", padding: "48px 40px" }}>
            <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "26px", fontWeight: 700, marginBottom: "16px" }}>
              How it works
            </h2>
            <ol style={{ textAlign: "left", maxWidth: "500px", margin: "0 auto 32px", paddingLeft: "20px", lineHeight: "2" }}>
              <li>A synthetic board meeting agenda is generated with realistic time allocations.</li>
              <li>You score each rubric item as you would in a real Time Use Evaluation.</li>
              <li>The system's own scores are revealed. Cohen's kappa is computed for each item.</li>
              <li>You receive specific feedback on every item where you and the system disagreed.</li>
              <li>Repeat until your rolling κ ≥ 0.70 across 5 consecutive scenarios.</li>
            </ol>
            <div
              style={{
                background: "var(--esb-light-bg)",
                borderRadius: "4px",
                padding: "16px 20px",
                marginBottom: "32px",
                fontSize: "14px",
                color: "var(--esb-text)",
                textAlign: "left",
              }}
            >
              <strong>Target threshold: κ ≥ 0.70</strong> — substantial agreement. This is the standard
              for certified Effective School Boards practitioners.
            </div>
            <button
              onClick={handleGenerateScenario}
              disabled={loading}
              className="btn-primary"
              style={{ fontSize: "16px", padding: "12px 40px", opacity: loading ? 0.7 : 1 }}
            >
              {loading ? "Generating scenario…" : "Start a Practice Scenario"}
            </button>
          </div>
        )}

        {/* Scoring stage */}
        {stage === "scoring" && scenario && (
          <div>
            {/* Meeting summary */}
            <div className="esb-card" style={{ marginBottom: "28px" }}>
              <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "22px", fontWeight: 700, marginBottom: "16px" }}>
                {scenario.scenario_data.district}
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm" style={{ marginBottom: "20px" }}>
                <Info label="Date" value={scenario.scenario_data.meeting_date} />
                <Info label="Type" value={scenario.scenario_data.meeting_type} />
                <Info label="Quorum" value={`${scenario.scenario_data.quorum_present}/${scenario.scenario_data.board_size}`} />
                <Info label="Total Time" value={`${scenario.scenario_data.total_minutes} min`} />
              </div>

              <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, marginBottom: "12px" }}>
                Agenda
              </h3>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}>
                <thead>
                  <tr style={{ background: "var(--esb-light-bg)" }}>
                    <th style={{ padding: "8px 12px", textAlign: "left", fontFamily: "var(--font-heading)", fontWeight: 700, borderBottom: "2px solid var(--esb-border)" }}>Item</th>
                    <th style={{ padding: "8px 12px", textAlign: "right", fontFamily: "var(--font-heading)", fontWeight: 700, borderBottom: "2px solid var(--esb-border)", width: "120px" }}>Minutes</th>
                    <th style={{ padding: "8px 12px", textAlign: "right", fontFamily: "var(--font-heading)", fontWeight: 700, borderBottom: "2px solid var(--esb-border)", width: "80px" }}>%</th>
                  </tr>
                </thead>
                <tbody>
                  {scenario.scenario_data.agenda_items.map((item, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid var(--esb-border)" }}>
                      <td style={{ padding: "8px 12px", color: "var(--esb-text)" }}>{item.title}</td>
                      <td style={{ padding: "8px 12px", textAlign: "right", color: "var(--esb-text)" }}>{item.allocated_minutes}</td>
                      <td style={{ padding: "8px 12px", textAlign: "right", color: "var(--esb-muted)" }}>
                        {Math.round((item.allocated_minutes / scenario.scenario_data.total_minutes) * 100)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Score each rubric item */}
            <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "22px", fontWeight: 700, marginBottom: "20px" }}>
              Your Scores
            </h2>
            {RUBRIC_ITEMS.map((item) => (
              <div key={item.id} className="esb-card" style={{ marginBottom: "20px" }}>
                <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "17px", fontWeight: 700, marginBottom: "4px" }}>
                  {item.label}
                  {item.inverse && (
                    <span
                      style={{
                        marginLeft: "8px",
                        fontSize: "11px",
                        background: "#fff3cd",
                        color: "#856404",
                        padding: "2px 8px",
                        borderRadius: "4px",
                      }}
                    >
                      Lower = Better
                    </span>
                  )}
                </h3>
                <p style={{ color: "var(--esb-muted)", fontSize: "14px", marginBottom: "16px" }}>
                  {item.description}
                </p>
                <div className="grid grid-cols-1 gap-2">
                  {item.options.map((opt) => (
                    <label
                      key={opt.score}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                        padding: "10px 14px",
                        border: `2px solid ${scores[item.id] === opt.score ? "var(--esb-primary)" : "var(--esb-border)"}`,
                        borderRadius: "4px",
                        cursor: "pointer",
                        background: scores[item.id] === opt.score ? "#f0f9ff" : "#fff",
                        transition: "all 0.2s",
                      }}
                    >
                      <input
                        type="radio"
                        name={item.id}
                        value={opt.score}
                        checked={scores[item.id] === opt.score}
                        onChange={() => setScores((prev) => ({ ...prev, [item.id]: opt.score }))}
                        style={{ accentColor: "var(--esb-primary)" }}
                      />
                      <span>
                        <strong style={{ color: "var(--esb-primary)", fontFamily: "var(--font-heading)" }}>
                          {opt.score}
                        </strong>
                        <span style={{ color: "var(--esb-text)", fontSize: "14px", marginLeft: "8px" }}>
                          {opt.label}
                        </span>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            ))}

            <div style={{ display: "flex", gap: "16px", marginTop: "8px" }}>
              <button
                onClick={handleSubmit}
                disabled={loading}
                className="btn-primary"
                style={{ fontSize: "16px", padding: "12px 40px", opacity: loading ? 0.7 : 1 }}
              >
                {loading ? "Scoring…" : "Submit Scores"}
              </button>
              <button
                onClick={() => setStage("landing")}
                style={{ background: "none", border: "2px solid var(--esb-border)", borderRadius: "4px", padding: "12px 24px", cursor: "pointer", fontFamily: "var(--font-heading)", fontSize: "15px" }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Results stage */}
        {stage === "results" && result && (
          <div>
            {/* Kappa summary */}
            <div
              className="esb-card"
              style={{
                marginBottom: "28px",
                borderLeft: `6px solid ${result.passed ? "#18d26e" : result.kappa >= 0.40 ? "#ffc107" : "#ed3c0d"}`,
              }}
            >
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: "52px", fontWeight: 700, fontFamily: "var(--font-heading)", color: result.passed ? "#18d26e" : "var(--esb-dark)" }}>
                    {result.kappa.toFixed(3)}
                  </div>
                  <div style={{ color: "var(--esb-muted)", fontSize: "14px" }}>Cohen's κ</div>
                </div>
                <div style={{ gridColumn: "span 2" }}>
                  <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "22px", fontWeight: 700, marginBottom: "8px" }}>
                    {result.passed ? "Passed ✓" : "Not yet — keep practicing"}
                  </h2>
                  <p style={{ color: "var(--esb-text)", marginBottom: "12px" }}>{result.message}</p>
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    {[
                      { label: "Poor", range: "< 0.40", active: result.kappa < 0.40 },
                      { label: "Moderate", range: "0.40–0.69", active: result.kappa >= 0.40 && result.kappa < 0.70 },
                      { label: "Substantial ✓", range: "≥ 0.70", active: result.kappa >= 0.70 },
                    ].map((tier) => (
                      <span
                        key={tier.label}
                        style={{
                          padding: "4px 12px",
                          borderRadius: "50px",
                          fontSize: "13px",
                          fontWeight: tier.active ? 700 : 400,
                          background: tier.active ? "var(--esb-primary)" : "var(--esb-light-bg)",
                          color: tier.active ? "#fff" : "var(--esb-muted)",
                          border: `1px solid ${tier.active ? "var(--esb-primary)" : "var(--esb-border)"}`,
                        }}
                      >
                        {tier.label} ({tier.range})
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Item-by-item breakdown */}
            <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "22px", fontWeight: 700, marginBottom: "20px" }}>
              Item Breakdown
            </h2>
            {RUBRIC_ITEMS.map((item) => {
              const sys = result.system_scores[item.id];
              const prac = (result as unknown as Record<string, unknown>);
              const pracScore = scenario?.scenario_data ? (Object.fromEntries(
                RUBRIC_ITEMS.map((i) => [i.id, {}])
              )[item.id] as Record<string, unknown>) : null;
              const itemKappa = result.item_kappas[item.id];
              const feedback = result.item_feedback[item.id];
              const agreed = feedback === "Correct.";

              return (
                <div
                  key={item.id}
                  className="esb-card"
                  style={{
                    marginBottom: "16px",
                    borderLeft: `4px solid ${agreed ? "#18d26e" : "#ed3c0d"}`,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                    <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, margin: 0 }}>
                      {item.label}
                    </h3>
                    <span style={{ color: agreed ? "#18d26e" : "#ed3c0d", fontWeight: 700, fontSize: "14px" }}>
                      {agreed ? "Agreement ✓" : `κ = ${(itemKappa ?? 0).toFixed(2)}`}
                    </span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <span style={{ color: "var(--esb-muted)", fontWeight: 600 }}>System: </span>
                      <span style={{ color: "var(--esb-primary)", fontWeight: 700 }}>{sys?.score ?? "—"}</span>
                      {sys && <span style={{ color: "var(--esb-text)", marginLeft: "6px" }}>— {sys.rationale}</span>}
                      {sys && <div style={{ color: "var(--esb-muted)", fontSize: "12px", marginTop: "2px" }}>{sys.minutes} min ({sys.pct_of_meeting}%)</div>}
                    </div>
                  </div>
                  {!agreed && (
                    <div
                      style={{
                        marginTop: "12px",
                        background: "#fff5f5",
                        borderRadius: "4px",
                        padding: "10px 14px",
                        fontSize: "14px",
                        color: "var(--esb-text)",
                      }}
                    >
                      {feedback}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Next actions */}
            <div style={{ display: "flex", gap: "16px", marginTop: "24px", flexWrap: "wrap" }}>
              <button onClick={handleGenerateScenario} disabled={loading} className="btn-primary" style={{ fontSize: "15px", padding: "12px 32px" }}>
                {loading ? "Generating…" : "Try Another Scenario"}
              </button>
              <button onClick={() => setStage("landing")} className="btn-outline" style={{ fontSize: "15px", padding: "12px 32px" }}>
                Back to Overview
              </button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: "36px", fontWeight: 700, fontFamily: "var(--font-heading)", color: color ?? "var(--esb-dark)" }}>
        {value}
      </div>
      <div style={{ color: "var(--esb-muted)", fontSize: "13px", fontFamily: "var(--font-heading)" }}>
        {label}
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: "12px", color: "var(--esb-muted)", fontWeight: 600, fontFamily: "var(--font-heading)", marginBottom: "2px" }}>
        {label}
      </div>
      <div style={{ color: "var(--esb-dark)", fontWeight: 600 }}>{value}</div>
    </div>
  );
}
