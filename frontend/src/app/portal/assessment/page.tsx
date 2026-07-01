"use client";

import { API_BASE } from "@/lib/api";

/**
 * The Great on Their Behalf Index — Self-Assessment
 *
 * CRITICAL: Indicative disclaimer MUST appear on every view of this page.
 * This is an unvalidated, self-scored instrument. Never remove or minimize
 * the disclaimer. See architecture v3.2 §2 and Sys-14 validation rule.
 */
import { useState } from "react";

type Stage = "intro" | "scoring" | "results";

// Practice definitions — band labels match BAND_LABELS in models/scoring.py
const PRACTICES = [
  {
    key: "focus_mindset",
    title: "Focus Mindset",
    description:
      "The board consistently focuses on student outcomes as its primary responsibility, rather than operational matters.",
    bands: [
      { score: 0, label: "Beginning Focus", description: "The board has not yet developed a consistent student-outcomes focus. Meetings are dominated by operational reports and routine approvals." },
      { score: 1, label: "Emerging Focus", description: "The board is beginning to direct attention to student outcomes but reverts frequently to operational topics. Uneven across meetings and members." },
      { score: 2, label: "Effective Focus", description: "The board consistently prioritizes student outcomes in its agenda and discussions. Most members actively redirect operational drift." },
      { score: 3, label: "Highly Effective Focus", description: "The board maintains an unwavering student-outcomes focus. Operational matters are confidently delegated. This norm is self-reinforcing across members and time." },
    ],
    conjunctive: false,
  },
  {
    key: "clarify",
    title: "Clarify Priorities",
    description:
      "The board sets and maintains clear goals for student outcomes AND clear guardrails for how the superintendent operates. Both must be well-formed.",
    bands: [
      { score: 0, label: "Beginning Clarity", description: "Goals and guardrails are absent, vague, or not formally adopted." },
      { score: 1, label: "Emerging Focus", description: "Some goals or guardrails exist but lack specificity, measurability, or formal adoption. Not consistently used to guide decisions." },
      { score: 2, label: "Effective Focus", description: "Goals and guardrails are clearly stated, formally adopted, and referenced in board work. Both are well-formed at this level." },
      { score: 3, label: "Highly Effective Focus", description: "Goals and guardrails are exemplary — ambitious, measurable, community-rooted, and actively used to evaluate superintendent performance and board decisions." },
    ],
    conjunctive: true,
    sub: [
      {
        key: "clarify_goals",
        label: "Goals",
        hint: "How well-formed are the board's student outcome goals?",
      },
      {
        key: "clarify_guardrails",
        label: "Guardrails",
        hint: "How well-formed are the board's guardrails for superintendent operation?",
      },
    ],
  },
  {
    key: "monitor",
    title: "Monitor Progress",
    description:
      "The board regularly reviews meaningful data on progress toward its goals and uses that data to inform decisions.",
    bands: [
      { score: 0, label: "Beginning Monitoring", description: "The board does not regularly review student outcome data. Decisions are made without reference to progress data." },
      { score: 1, label: "Emerging Focus", description: "The board occasionally reviews data but lacks a systematic approach. Data is presented but not deeply analyzed or linked to board decisions." },
      { score: 2, label: "Effective Focus", description: "The board has a regular data review cadence. Discussions connect data to goals and inform decisions. Board asks probing questions." },
      { score: 3, label: "Highly Effective Focus", description: "Monitoring is rigorous, systematic, and embedded in board culture. The board demands quality data, identifies trends, and adjusts course with precision." },
    ],
    conjunctive: false,
  },
  {
    key: "align",
    title: "Align Resources",
    description:
      "The board ensures that budget, staffing, and policy decisions are aligned to its student outcome goals.",
    bands: [
      { score: 0, label: "Beginning Alignment", description: "Resource decisions are made without explicit connection to student outcome goals. Budget and staffing follow historical patterns." },
      { score: 1, label: "Emerging Focus", description: "Some resource decisions reference goals but alignment is inconsistent. Budget discussions don't consistently start from goals." },
      { score: 2, label: "Effective Focus", description: "The board systematically reviews resource alignment. Policy and budget decisions include explicit goal-connection rationale." },
      { score: 3, label: "Highly Effective Focus", description: "Resource allocation is rigorously goal-driven. The board proactively realigns resources in response to monitoring data. Alignment is a cultural expectation." },
    ],
    conjunctive: false,
  },
  {
    key: "communicate",
    title: "Communicate Results",
    description:
      "The board communicates clearly and consistently with the community about goals, progress, and what the board is doing about it.",
    bands: [
      { score: 0, label: "Beginning Communication", description: "The board does not proactively communicate goals or progress to the community. Communication is reactive or absent." },
      { score: 1, label: "Emerging Focus", description: "Some communication occurs but is infrequent or lacks connection to goals and data. Not yet a consistent board responsibility." },
      { score: 2, label: "Effective Focus", description: "The board communicates regularly about goals and progress. Multiple channels used. Community has access to outcome data and board priorities." },
      { score: 3, label: "Highly Effective Focus", description: "Communication is proactive, multi-channel, and data-rich. The board builds genuine community understanding of and investment in student outcome goals." },
    ],
    conjunctive: false,
  },
] as const;

type ScoreMap = Record<string, number>;

type ScoredPractice = {
  practice: string;
  raw_band: number;
  score: number;
  ceiling: number;
  band_label: string;
};

type AssessmentResult = {
  session_id: string;
  total_score: number;
  composite_band: number;
  practice_scores: ScoredPractice[];
  clarify_detail: { goals_band: number; guardrails_band: number; conjunctive_band: number };
  indicative_disclaimer: string;
};

const CEILINGS: Record<string, number> = {
  focus_mindset: 10,
  clarify: 20,
  monitor: 40,
  align: 20,
  communicate: 10,
};

const COMPOSITE_LABELS = ["", "Beginning Focus", "Emerging Focus", "Effective Focus", "Highly Effective Focus"];

export default function AssessmentPage() {
  const [stage, setStage] = useState<Stage>("intro");
  const [scores, setScores] = useState<ScoreMap>({});
  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [districtId, setDistrictId] = useState("");
  const [districtLabel, setDistrictLabel] = useState("");
  const [districtQuery, setDistrictQuery] = useState("");
  const [districtResults, setDistrictResults] = useState<{ id: string; name: string; state: string }[]>([]);
  const [districtSearching, setDistrictSearching] = useState(false);
  const [creatingDistrict, setCreatingDistrict] = useState(false);
  const [newDistrictState, setNewDistrictState] = useState("");

  function getToken() {
    if (typeof window === "undefined") return null;
    return sessionStorage.getItem("esb_token");
  }

  async function searchDistricts(q: string) {
    setDistrictQuery(q);
    if (q.trim().length < 2) {
      setDistrictResults([]);
      return;
    }
    setDistrictSearching(true);
    try {
      const token = getToken();
      const res = await fetch(`${API_BASE}/api/districts/search?q=${encodeURIComponent(q)}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) setDistrictResults(await res.json());
    } catch {
      // best-effort search; leave results as-is
    } finally {
      setDistrictSearching(false);
    }
  }

  async function createDistrict() {
    if (!districtQuery.trim() || !newDistrictState.trim()) return;
    setCreatingDistrict(true);
    setError("");
    try {
      const token = getToken();
      const res = await fetch(`${API_BASE}/api/districts/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ name: districtQuery.trim(), state: newDistrictState.trim().toUpperCase() }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "Failed to create district.");
      const d = await res.json();
      setDistrictId(d.id);
      setDistrictLabel(`${d.name}, ${d.state}`);
      setDistrictResults([]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create district.");
    } finally {
      setCreatingDistrict(false);
    }
  }

  async function handleSubmit() {
    if (!districtId) {
      setError("Please select or add your district before submitting.");
      return;
    }
    const missing = PRACTICES.filter((p) => {
      if (p.conjunctive) {
        return scores["clarify_goals"] === undefined || scores["clarify_guardrails"] === undefined;
      }
      return scores[p.key] === undefined;
    });
    if (missing.length > 0) {
      setError(`Please complete all practices before submitting.`);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const token = getToken();
      const res = await fetch(`${API_BASE}/api/assessments/indicative`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          district_id: districtId,
          focus_mindset: scores.focus_mindset ?? 0,
          clarify_goals: scores.clarify_goals ?? 0,
          clarify_guardrails: scores.clarify_guardrails ?? 0,
          monitor: scores.monitor ?? 0,
          align: scores.align ?? 0,
          communicate: scores.communicate ?? 0,
        }),
      });
      if (!res.ok) throw new Error((await res.json()).detail ?? "Failed to submit.");
      const data = await res.json();
      setResult(data);
      setStage("results");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Submission failed.");
    } finally {
      setLoading(false);
    }
  }

  const DISCLAIMER =
    "This is an indicative, self-scored assessment. It has not been validated or benchmarked by Effective School Boards. Results reflect your board's own perceptions and should be interpreted accordingly. A Certified Assessment, administered by a credentialed Effective School Boards practitioner, provides a validated picture of your board's performance.";

  return (
    <div>
      {/* Page header */}
      <div style={{ background: "var(--esb-section-dark)", padding: "40px 0 30px", color: "#fff" }}>
        <div className="container mx-auto px-4">
          <h1 style={{ fontFamily: "var(--font-heading)", fontSize: "34px", fontWeight: 700, color: "#fff", margin: 0 }}>
            The Great on Their Behalf Index
          </h1>
          <p style={{ color: "#aaaaaa", marginTop: "8px", marginBottom: 0 }}>
            Indicative Self-Assessment · Five Practices
          </p>
        </div>
      </div>

      {/* Disclaimer — always visible */}
      <div style={{ background: "#fff8e1", borderBottom: "2px solid #ffc107" }}>
        <div className="container mx-auto px-4 py-3">
          <p style={{ margin: 0, fontSize: "14px", color: "#5d4037" }}>
            <strong>Indicative Assessment Only.</strong> {DISCLAIMER}
          </p>
        </div>
      </div>

      <div className="container mx-auto px-4 py-10">
        {error && (
          <div style={{ background: "#fff5f5", border: "1px solid #ed3c0d", borderRadius: "4px", padding: "12px 16px", color: "#ed3c0d", marginBottom: "24px", fontSize: "14px" }}>
            {error}
          </div>
        )}

        {/* Intro stage */}
        {stage === "intro" && (
          <div className="esb-card" style={{ maxWidth: "700px", margin: "0 auto" }}>
            <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "26px", fontWeight: 700, marginBottom: "16px" }}>
              About this Assessment
            </h2>
            <p style={{ color: "var(--esb-text)", lineHeight: "1.8", marginBottom: "16px" }}>
              The Great on Their Behalf Index measures your school board across five practices that
              research and practitioner experience link to improved student outcomes. Each practice
              is rated on a 4-level scale from Beginning to Highly Effective.
            </p>
            <p style={{ color: "var(--esb-text)", lineHeight: "1.8", marginBottom: "24px" }}>
              <strong>Clarify Priorities</strong> uses a conjunctive rubric — you will score your
              board separately on Goals and Guardrails. The lower of the two determines your
              Clarify Priorities score.
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "12px", marginBottom: "32px" }}>
              {PRACTICES.map((p) => (
                <div key={p.key} style={{ textAlign: "center", padding: "16px 8px", background: "var(--esb-light-bg)", borderRadius: "4px" }}>
                  <div style={{ fontSize: "22px", fontWeight: 700, color: "var(--esb-primary)", fontFamily: "var(--font-heading)" }}>
                    {CEILINGS[p.key]}
                  </div>
                  <div style={{ fontSize: "12px", color: "var(--esb-muted)", marginTop: "4px" }}>{p.title}</div>
                </div>
              ))}
            </div>
            <div style={{ marginBottom: "24px", borderTop: "1px solid var(--esb-border)", paddingTop: "20px" }}>
              <label style={{ display: "block", fontWeight: 600, marginBottom: "8px" }}>District</label>
              {districtId ? (
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                  <span style={{ fontSize: "14px" }}>{districtLabel}</span>
                  <button
                    onClick={() => { setDistrictId(""); setDistrictLabel(""); setDistrictQuery(""); }}
                    style={{ background: "none", border: "1px solid var(--esb-border)", borderRadius: "4px", padding: "4px 10px", cursor: "pointer", fontSize: "13px" }}
                  >
                    Change
                  </button>
                </div>
              ) : (
                <>
                  <input
                    type="text"
                    className="esb-input"
                    placeholder="Search for your district by name…"
                    value={districtQuery}
                    onChange={(e) => searchDistricts(e.target.value)}
                    style={{ width: "100%", marginBottom: "8px" }}
                  />
                  {districtSearching && <div style={{ fontSize: "13px", color: "var(--esb-muted)" }}>Searching…</div>}
                  {districtResults.length > 0 && (
                    <div style={{ border: "1px solid var(--esb-border)", borderRadius: "4px", marginBottom: "8px" }}>
                      {districtResults.map((d) => (
                        <div
                          key={d.id}
                          onClick={() => { setDistrictId(d.id); setDistrictLabel(`${d.name}, ${d.state}`); setDistrictResults([]); }}
                          style={{ padding: "8px 12px", cursor: "pointer", borderBottom: "1px solid var(--esb-border)", fontSize: "14px" }}
                        >
                          {d.name}, {d.state}
                        </div>
                      ))}
                    </div>
                  )}
                  {districtQuery.trim().length >= 2 && !districtSearching && districtResults.length === 0 && (
                    <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                      <span style={{ fontSize: "13px", color: "var(--esb-muted)" }}>No match — add it:</span>
                      <input
                        type="text"
                        className="esb-input"
                        placeholder="State (e.g. TX)"
                        maxLength={2}
                        value={newDistrictState}
                        onChange={(e) => setNewDistrictState(e.target.value)}
                        style={{ width: "70px" }}
                      />
                      <button
                        onClick={createDistrict}
                        disabled={creatingDistrict || newDistrictState.trim().length !== 2}
                        className="btn-outline"
                        style={{ fontSize: "13px", padding: "6px 14px" }}
                      >
                        {creatingDistrict ? "Adding…" : `Add "${districtQuery.trim()}"`}
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
            <button
              onClick={() => setStage("scoring")}
              className="btn-primary"
              disabled={!districtId}
              style={{ fontSize: "16px", padding: "12px 40px", opacity: districtId ? 1 : 0.5, cursor: districtId ? "pointer" : "not-allowed" }}
            >
              Begin Assessment
            </button>
          </div>
        )}

        {/* Scoring stage */}
        {stage === "scoring" && (
          <div>
            {PRACTICES.map((practice, idx) => (
              <div key={practice.key} className="esb-card" style={{ marginBottom: "28px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                  <div>
                    <span style={{ fontFamily: "var(--font-heading)", fontSize: "13px", fontWeight: 600, color: "var(--esb-muted)", textTransform: "uppercase", letterSpacing: "1px" }}>
                      Practice {idx + 1} of {PRACTICES.length} · Max {CEILINGS[practice.key]} pts
                    </span>
                    <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "22px", fontWeight: 700, margin: "4px 0 8px" }}>
                      {practice.title}
                    </h2>
                  </div>
                  {practice.conjunctive && (
                    <span style={{ background: "#e3f2fd", color: "#1976d2", fontSize: "12px", fontWeight: 600, padding: "4px 10px", borderRadius: "4px", whiteSpace: "nowrap" }}>
                      Conjunctive Rubric
                    </span>
                  )}
                </div>
                <p style={{ color: "var(--esb-text)", fontSize: "15px", marginBottom: "20px" }}>{practice.description}</p>

                {practice.conjunctive ? (
                  // Clarify Priorities: two sub-scores
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
                    {practice.sub.map((sub) => (
                      <div key={sub.key}>
                        <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, marginBottom: "4px" }}>
                          {sub.label}
                        </h3>
                        <p style={{ color: "var(--esb-muted)", fontSize: "13px", marginBottom: "12px" }}>{sub.hint}</p>
                        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                          {practice.bands.map((band) => (
                            <BandOption
                              key={band.score}
                              band={band}
                              selected={scores[sub.key] === band.score}
                              onChange={() => setScores((prev) => ({ ...prev, [sub.key]: band.score }))}
                              name={sub.key}
                            />
                          ))}
                        </div>
                      </div>
                    ))}
                    {scores.clarify_goals !== undefined && scores.clarify_guardrails !== undefined && (
                      <div style={{ gridColumn: "span 2", background: "#e8f5e9", borderRadius: "4px", padding: "12px 16px" }}>
                        <strong style={{ color: "#2e7d32", fontSize: "14px" }}>
                          Conjunctive result: Band {Math.min(scores.clarify_goals, scores.clarify_guardrails)} (lower of Goals and Guardrails)
                        </strong>
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {practice.bands.map((band) => (
                      <BandOption
                        key={band.score}
                        band={band}
                        selected={scores[practice.key] === band.score}
                        onChange={() => setScores((prev) => ({ ...prev, [practice.key]: band.score }))}
                        name={practice.key}
                      />
                    ))}
                  </div>
                )}
              </div>
            ))}

            <div style={{ display: "flex", gap: "16px" }}>
              <button
                onClick={handleSubmit}
                disabled={loading}
                className="btn-primary"
                style={{ fontSize: "16px", padding: "12px 40px", opacity: loading ? 0.7 : 1 }}
              >
                {loading ? "Scoring…" : "Submit Assessment"}
              </button>
              <button onClick={() => { setStage("intro"); setScores({}); }}
                style={{ background: "none", border: "2px solid var(--esb-border)", borderRadius: "4px", padding: "12px 24px", cursor: "pointer", fontFamily: "var(--font-heading)" }}>
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Results stage */}
        {stage === "results" && result && (
          <div>
            {/* Score summary */}
            <div className="esb-card" style={{ marginBottom: "28px", textAlign: "center" }}>
              <div style={{ display: "flex", width: "120px", height: "120px", borderRadius: "50%", border: "6px solid var(--esb-primary)", alignItems: "center", justifyContent: "center", margin: "0 auto 16px", flexDirection: "column" }}>
                <div style={{ fontSize: "40px", fontWeight: 700, fontFamily: "var(--font-heading)", color: "var(--esb-primary)", lineHeight: 1 }}>
                  {result.total_score}
                </div>
                <div style={{ fontSize: "13px", color: "var(--esb-muted)" }}>/ 100</div>
              </div>
              <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "28px", fontWeight: 700, margin: "0 0 4px" }}>
                {COMPOSITE_LABELS[result.composite_band]}
              </h2>
              <p style={{ color: "var(--esb-muted)" }}>Composite result across all five practices</p>
              <div style={{ background: "#fff8e1", border: "1px solid #ffc107", borderRadius: "4px", padding: "12px 16px", marginTop: "20px", fontSize: "13px", color: "#5d4037", textAlign: "left" }}>
                <strong>Remember:</strong> {result.indicative_disclaimer}
              </div>
            </div>

            {/* Practice breakdown */}
            <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "22px", fontWeight: 700, marginBottom: "20px" }}>
              Practice Breakdown
            </h2>
            {result.practice_scores.map((ps) => (
              <div key={ps.practice} className="esb-card" style={{ marginBottom: "16px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "17px", fontWeight: 700, margin: "0 0 4px" }}>
                      {PRACTICES.find((p) => p.key === ps.practice)?.title ?? ps.practice}
                    </h3>
                    <span style={{ fontSize: "14px", color: "var(--esb-primary)", fontWeight: 600 }}>{ps.band_label}</span>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: "28px", fontWeight: 700, fontFamily: "var(--font-heading)", color: "var(--esb-dark)" }}>
                      {ps.score}
                    </div>
                    <div style={{ fontSize: "13px", color: "var(--esb-muted)" }}>/ {ps.ceiling}</div>
                  </div>
                </div>
                {/* Score bar */}
                <div style={{ marginTop: "12px", background: "var(--esb-light-bg)", borderRadius: "4px", height: "8px", overflow: "hidden" }}>
                  <div style={{ width: `${(ps.score / ps.ceiling) * 100}%`, height: "100%", background: "var(--esb-primary)", transition: "width 0.5s" }} />
                </div>
                {ps.practice === "clarify" && result.clarify_detail && (
                  <div style={{ marginTop: "10px", fontSize: "13px", color: "var(--esb-muted)" }}>
                    Goals: Band {result.clarify_detail.goals_band} · Guardrails: Band {result.clarify_detail.guardrails_band} · Conjunctive: Band {result.clarify_detail.conjunctive_band}
                  </div>
                )}
              </div>
            ))}

            {/* CTA to certified */}
            <div className="esb-card" style={{ marginTop: "32px", background: "var(--esb-section-dark)", color: "#fff", textAlign: "center", padding: "40px 30px" }}>
              <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "22px", fontWeight: 700, color: "#fff", marginBottom: "12px" }}>
                Want a Validated Picture?
              </h3>
              <p style={{ color: "#aaaaaa", marginBottom: "24px" }}>
                A Certified Assessment — administered by a credentialed Effective School Boards practitioner —
                gives your board a validated, benchmarked view of its performance.
              </p>
              <a href="https://effectiveschoolboards.com/coaches/find/" target="_blank" rel="noopener noreferrer" className="btn-primary">
                Find a Practitioner
              </a>
            </div>

            <div style={{ marginTop: "24px", display: "flex", gap: "16px" }}>
              <button onClick={() => { setStage("intro"); setScores({}); setResult(null); }} className="btn-outline">
                Take Assessment Again
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function BandOption({
  band, selected, onChange, name,
}: {
  band: { score: number; label: string; description: string };
  selected: boolean;
  onChange: () => void;
  name: string;
}) {
  return (
    <label
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "12px",
        padding: "12px 16px",
        border: `2px solid ${selected ? "var(--esb-primary)" : "var(--esb-border)"}`,
        borderRadius: "4px",
        cursor: "pointer",
        background: selected ? "#f0f9ff" : "#fff",
        transition: "all 0.2s",
      }}
    >
      <input type="radio" name={name} checked={selected} onChange={onChange} style={{ accentColor: "var(--esb-primary)", marginTop: "2px", flexShrink: 0 }} />
      <div>
        <div style={{ fontFamily: "var(--font-heading)", fontWeight: 700, fontSize: "15px", color: selected ? "var(--esb-primary)" : "var(--esb-dark)", marginBottom: "2px" }}>
          Band {band.score}: {band.label}
        </div>
        <div style={{ fontSize: "13px", color: "var(--esb-text)", lineHeight: "1.5" }}>{band.description}</div>
      </div>
    </label>
  );
}
