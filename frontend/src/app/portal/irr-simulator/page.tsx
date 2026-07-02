"use client";

/**
 * Time Use Evaluation IRR Simulator — M20
 *
 * (Named "Time Use Evaluation IRR Simulator" specifically because a
 * separate GOTB Index Assessment IRR Simulator is planned later.)
 *
 * Three stages:
 *   1. Landing / progress overview
 *   2. Classification — practitioner reads synthetic meeting MINUTES (not
 *      an agenda — an agenda can't tell you how long anything took) and
 *      enters total minutes per Activity, matching the real ESB Time Use
 *      Eval form's Activity taxonomy.
 *   3. Results — kappa, per-item feedback, system vs. practitioner comparison
 */
import { useState, useEffect } from "react";
import { API_BASE } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

type Stage = "landing" | "scoring" | "results";

type MinuteItem = {
  description: string;
  minutes: number;
};

type ScenarioData = {
  district: string;
  meeting_date: string;
  meeting_type: string;
  quorum_present: number;
  board_size: number;
  total_minutes: number;
  minute_items: MinuteItem[];
  notes: string;
};

type ScenarioOut = {
  scenario_id: string;
  scenario_data: ScenarioData;
  item_count: number;
};

type SystemItemScore = { minutes: number; pct_of_meeting: number };

type AttemptResult = {
  attempt_id: string;
  kappa: number;
  passed: boolean;
  item_kappas: Record<string, number>;
  item_feedback: Record<string, string>;
  system_scores: Record<string, SystemItemScore> & {
    _totals?: { student_outcomes_minutes: number; student_outcomes_pct: number; public_meeting_minutes: number };
  };
  kappa_threshold: number;
  message: string;
};

type Progress = {
  attempts_total: number;
  attempts_passed: number;
  rolling_kappa: number | null;
  certified_at: string | null;
};

// ── Activity taxonomy (mirrors backend TIME_USE_ITEMS — verbatim from the
// real ESB Board Monthly Time Use Evaluation form) ────────────────────────────

type ActivityItem = { id: string; framework: string; label: string; description: string; excludedFromTotals?: boolean };

const ACTIVITY_ITEMS: ActivityItem[] = [
  { id: "board_self_eval", framework: "Focus Mindset", label: "Board Self Eval",
    description: "Quarterly and/or annual Board self-evaluation using the effective school boards framework instrument." },
  { id: "effective_time_use_eval", framework: "Focus Mindset", label: "Effective Time Use Eval",
    description: "Meeting evaluation using this time use instrument." },
  { id: "board_training", framework: "Focus Mindset", label: "Board Training",
    description: "Training for the Board on the effective school boards framework and related topics." },
  { id: "board_led_community_training", framework: "Focus Mindset", label: "Board-led Community Training",
    description: "Board-hosted and Board Member-led or co-led training on the effective school boards framework and related topics." },

  { id: "community_listening_goals", framework: "Clarify Priorities 1: Vision & Goals", label: "Community Listening",
    description: "Two-way communication opportunity where Board Members listen for and discuss the vision/values of their students, families, staff and community members — related to the community's vision, setting Goals, and/or monitoring Goals." },
  { id: "data_eval_goals", framework: "Clarify Priorities 1: Vision & Goals", label: "Data Eval",
    description: "Analyzing student data that speaks to the highest need, highest leverage areas." },
  { id: "goal_setting", framework: "Clarify Priorities 1: Vision & Goals", label: "Goal Setting",
    description: "Learning, data gathering, reviewing, discussing, and/or selecting goals and accepting interim goals." },

  { id: "community_listening_guardrails", framework: "Clarify Priorities 2: Values & Guardrails", label: "Community Listening",
    description: "Two-way communication opportunity where Board Members listen for and discuss the vision/values of their students, families, staff and community members — related to setting and/or monitoring Guardrails." },
  { id: "data_eval_guardrails", framework: "Clarify Priorities 2: Values & Guardrails", label: "Data Eval",
    description: "Analyzing system data that speaks to the highest need, highest leverage areas." },
  { id: "guardrail_setting", framework: "Clarify Priorities 2: Values & Guardrails", label: "Guardrail Setting",
    description: "Learning, data gathering, reviewing, discussing, and/or selecting guardrails and accepting interim guardrails." },

  { id: "goal_monitoring", framework: "Monitor Progress", label: "Goal Monitoring",
    description: "Learning, data gathering, reviewing, discussing, and/or approving/not approving goal monitoring reports in accordance with the monitoring calendar." },
  { id: "guardrail_monitoring", framework: "Monitor Progress", label: "Guardrail Monitoring",
    description: "Learning, data gathering, reviewing, discussing, and/or approving/not approving guardrail monitoring reports in accordance with the monitoring calendar." },
  { id: "superintendent_eval", framework: "Monitor Progress", label: "Superintendent Eval",
    description: "Annual evaluation of Superintendent/school system performance." },

  { id: "voting", framework: "Align Resources", label: "Voting",
    description: "The Board debating and/or voting on any item. Voting on goal/guardrail adoption and/or scheduled monitoring reports & evals are counted elsewhere, not here — all other incidents of debating/voting are never a form of goals/guardrails “monitoring.”" },
  { id: "policy_review", framework: "Align Resources", label: "Policy Review/Diet",
    description: "The Board evaluating whether policies align with the goals, guardrails, or legal requirements." },
  { id: "budget_review", framework: "Align Resources", label: "Budget Review",
    description: "The Board evaluating whether the budget aligns with the goals and guardrails." },

  { id: "community_engagement", framework: "Communicate Results", label: "Community Engagement",
    description: "Two-way communication opportunity hosted by Board Members where they listen for and discuss the vision/values of their students, families, staff and community members, related to board work, but that is NOT setting or monitoring goals and guardrails. Must be genuinely two-way and board-hosted — a one-way public comment period where the board listens without dialogue does not meet this definition; that time is “Other.”" },
  { id: "community_outreach", framework: "Communicate Results", label: "Community Outreach",
    description: "Two-way communication opportunity where Board Members go to community-hosted meetings to listen for and discuss the vision/values of their students, families, staff and community members, related to board work, but that is NOT setting or monitoring goals or guardrails. Must be genuinely two-way — the board attending and passively observing a community event does not meet this definition." },

  { id: "closed_session", framework: "Other", label: "Closed Session",
    description: "Time spent in non-public meetings, consistent with open meetings laws. Not counted in Total Public Meeting Minutes.", excludedFromTotals: true },
  { id: "other", framework: "Other", label: "Other",
    description: "Any time spent on an activity that is not one of the above — including one-way public comment periods, procedural items (call to order, roll call, adjournment), and consent-agenda approval that isn't itself a Voting deliberation." },
];

const FRAMEWORK_ORDER = [
  "Focus Mindset",
  "Clarify Priorities 1: Vision & Goals",
  "Clarify Priorities 2: Values & Guardrails",
  "Monitor Progress",
  "Align Resources",
  "Communicate Results",
  "Other",
];

// Per the source form's own formula: "Total Student Outcomes-focused Minutes"
// = Goal Setting & Goal Monitoring combined — nothing else counts, even
// though other Activities (Guardrail Setting, Data Eval, etc.) are also
// student-outcomes-adjacent work.
const STUDENT_OUTCOMES_IDS = ["goal_setting", "goal_monitoring"];

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
  const [minutes, setMinutes] = useState<Record<string, number>>({});
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
      setMinutes({});
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
    setLoading(true);
    setError("");
    try {
      const practitioner_scores = Object.fromEntries(
        ACTIVITY_ITEMS.map((item) => [item.id, { minutes: minutes[item.id] ?? 0 }])
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
            Time Use Evaluation IRR Simulator
          </h1>
          <p style={{ color: "#aaaaaa", marginTop: "8px", marginBottom: 0 }}>
            Practice inter-rater reliability classifying board meeting minutes by Time Use Activity
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
            <ol style={{ textAlign: "left", maxWidth: "540px", margin: "0 auto 32px", paddingLeft: "20px", lineHeight: "2" }}>
              <li>You&apos;ll read a synthetic set of board meeting <strong>minutes</strong> — narrative blocks
                describing what the board actually did, with the time each block took.</li>
              <li>For each time block, decide which Time Use Activity it belongs to, using the exact
                Activity descriptions provided — some blocks are deliberately close calls that only
                resolve correctly against the definition, not the label.</li>
              <li>Enter the total minutes you&apos;d attribute to each Activity across the whole meeting.</li>
              <li>The system&apos;s own minute allocations are revealed. Agreement (κ) is computed per Activity.</li>
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

              <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, marginBottom: "6px" }}>
                Meeting Minutes
              </h3>
              <p style={{ color: "var(--esb-muted)", fontSize: "13px", marginBottom: "12px" }}>
                These are minutes, not an agenda — each block describes what the board actually did and how
                long it took. Read carefully: the description, not the topic label, determines the correct
                Activity classification. Add up the minutes for every block you assign to an Activity below.
              </p>
              <div>
                {scenario.scenario_data.minute_items.map((item, i) => (
                  <div key={i} style={{ display: "flex", gap: "16px", padding: "10px 0", borderBottom: i < scenario.scenario_data.minute_items.length - 1 ? "1px solid var(--esb-border)" : "none" }}>
                    <span style={{ color: "var(--esb-text)", fontSize: "14px", lineHeight: "1.6", flex: 1 }}>{item.description}</span>
                    <span style={{ color: "var(--esb-primary)", fontWeight: 700, fontSize: "14px", flexShrink: 0, whiteSpace: "nowrap" }}>{item.minutes} min</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Classify each block into total minutes per Activity */}
            <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "22px", fontWeight: 700, marginBottom: "8px" }}>
              Classify by Activity
            </h2>
            <p style={{ color: "var(--esb-muted)", fontSize: "14px", marginBottom: "20px" }}>
              For each Activity below, enter the total minutes from the meeting minutes above that belong
              to it. Leave at 0 for anything that didn&apos;t occur.
            </p>

            {FRAMEWORK_ORDER.map((framework) => (
              <div key={framework} className="esb-card" style={{ marginBottom: "20px" }}>
                <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, marginBottom: "14px", color: "var(--esb-primary)" }}>
                  {framework}
                </h3>
                {ACTIVITY_ITEMS.filter((a) => a.framework === framework).map((item) => (
                  <div key={item.id} style={{ display: "flex", gap: "16px", alignItems: "flex-start", marginBottom: "14px", paddingBottom: "14px", borderBottom: "1px solid var(--esb-border)" }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 700, fontSize: "14px", marginBottom: "2px" }}>
                        {item.label}
                        {item.excludedFromTotals && (
                          <span style={{ marginLeft: "8px", fontSize: "11px", background: "var(--esb-light-bg)", color: "var(--esb-muted)", padding: "2px 8px", borderRadius: "4px" }}>
                            excluded from totals
                          </span>
                        )}
                      </div>
                      <div style={{ color: "var(--esb-muted)", fontSize: "13px", lineHeight: "1.5" }}>{item.description}</div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
                      <input
                        type="number"
                        min={0}
                        className="esb-input"
                        value={minutes[item.id] ?? 0}
                        onChange={(e) => setMinutes((prev) => ({ ...prev, [item.id]: Math.max(0, parseInt(e.target.value, 10) || 0) }))}
                        style={{ width: "70px", textAlign: "right" }}
                      />
                      <span style={{ color: "var(--esb-muted)", fontSize: "13px" }}>min</span>
                    </div>
                  </div>
                ))}
              </div>
            ))}

            {/* Auto-calculated totals — matches the source form's own bottom rows, not editable */}
            <div className="esb-card" style={{ marginBottom: "20px", background: "var(--esb-light-bg)" }}>
              {(() => {
                const studentOutcomesMinutes = STUDENT_OUTCOMES_IDS.reduce((sum, id) => sum + (minutes[id] ?? 0), 0);
                const publicMeetingMinutesSoFar = ACTIVITY_ITEMS
                  .filter((a) => !a.excludedFromTotals)
                  .reduce((sum, a) => sum + (minutes[a.id] ?? 0), 0);
                const totalMinutes = scenario.scenario_data.total_minutes;
                const remaining = totalMinutes - publicMeetingMinutesSoFar;
                return (
                  <>
                    <TotalRow
                      label="Total Student Outcomes-focused Minutes"
                      sublabel="Goal Setting + Goal Monitoring combined"
                      value={`${studentOutcomesMinutes}/${totalMinutes}`}
                    />
                    <TotalRow
                      label="Total Public Meeting Minutes"
                      sublabel="All Activities above except Closed Session"
                      value={`${publicMeetingMinutesSoFar}/${totalMinutes}`}
                      last
                    />
                    {remaining !== 0 && (
                      <p style={{ color: remaining > 0 ? "var(--esb-muted)" : "#c62828", fontSize: "13px", margin: "10px 0 0" }}>
                        {remaining > 0
                          ? `${remaining} minute${remaining === 1 ? "" : "s"} from the meeting minutes above still unaccounted for.`
                          : `You've allocated ${Math.abs(remaining)} more minute${Math.abs(remaining) === 1 ? "" : "s"} than the meeting actually ran — check for double-counting.`}
                      </p>
                    )}
                  </>
                );
              })()}
            </div>

            <div style={{ display: "flex", gap: "16px", marginTop: "8px" }}>
              <button
                onClick={handleSubmit}
                disabled={loading}
                className="btn-primary"
                style={{ fontSize: "16px", padding: "12px 40px", opacity: loading ? 0.7 : 1 }}
              >
                {loading ? "Scoring…" : "Submit Classification"}
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
                  <div style={{ color: "var(--esb-muted)", fontSize: "14px" }}>Agreement (κ)</div>
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
                  {result.system_scores._totals && (
                    <p style={{ color: "var(--esb-muted)", fontSize: "13px", marginTop: "12px" }}>
                      Student-outcomes-focused minutes (Goal Setting + Goal Monitoring):{" "}
                      <strong>{result.system_scores._totals.student_outcomes_minutes} min ({result.system_scores._totals.student_outcomes_pct}%)</strong> of{" "}
                      {result.system_scores._totals.public_meeting_minutes} public meeting minutes.
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Item-by-item breakdown */}
            <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "22px", fontWeight: 700, marginBottom: "20px" }}>
              Activity Breakdown
            </h2>
            {ACTIVITY_ITEMS.map((item) => {
              const sys = result.system_scores[item.id];
              const yourMinutes = minutes[item.id] ?? 0;
              const feedback = result.item_feedback[item.id];
              const agreed = feedback === "Correct.";
              if ((sys?.minutes ?? 0) === 0 && yourMinutes === 0) return null; // not in play — skip from the review list

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
                    <div>
                      <div style={{ fontSize: "12px", color: "var(--esb-muted)", fontFamily: "var(--font-heading)" }}>{item.framework}</div>
                      <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, margin: 0 }}>
                        {item.label}
                      </h3>
                    </div>
                    <span style={{ color: agreed ? "#18d26e" : "#ed3c0d", fontWeight: 700, fontSize: "14px" }}>
                      {agreed ? "Agreement ✓" : `κ = ${(result.item_kappas[item.id] ?? 0).toFixed(2)}`}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-sm" style={{ marginBottom: "8px" }}>
                    <div>
                      <span style={{ color: "var(--esb-muted)", fontWeight: 600 }}>System: </span>
                      <span style={{ color: "var(--esb-primary)", fontWeight: 700 }}>{sys?.minutes ?? 0} min</span>
                      <span style={{ color: "var(--esb-muted)", fontSize: "12px", marginLeft: "6px" }}>({sys?.pct_of_meeting ?? 0}%)</span>
                    </div>
                    <div>
                      <span style={{ color: "var(--esb-muted)", fontWeight: 600 }}>You: </span>
                      <span style={{ fontWeight: 700 }}>{yourMinutes} min</span>
                    </div>
                  </div>
                  {!agreed && (
                    <div
                      style={{
                        marginTop: "8px",
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

function TotalRow({ label, sublabel, value, last }: { label: string; sublabel: string; value: string; last?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: last ? "none" : "1px solid var(--esb-border)" }}>
      <div>
        <div style={{ fontWeight: 700, fontSize: "14px" }}>{label}</div>
        <div style={{ color: "var(--esb-muted)", fontSize: "12px" }}>{sublabel}</div>
      </div>
      <div style={{ fontWeight: 700, fontSize: "16px", fontFamily: "var(--font-heading)", color: "var(--esb-primary)" }}>{value}</div>
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
