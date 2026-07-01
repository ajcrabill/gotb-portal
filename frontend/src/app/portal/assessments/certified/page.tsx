"use client";

import { API_BASE } from "@/lib/api";

/**
 * Certified Assessment — practitioner-administered, validated tier.
 * NEVER show "indicative" disclaimer here. Show the certified disclaimer instead.
 * Only accessible to certified_practitioner and above.
 */
import { useState } from "react";

type Stage = "setup" | "scoring" | "results";

const PRACTICES = [
  {
    key: "focus_mindset",
    title: "Focus Mindset",
    description: "The board consistently focuses on student outcomes as its primary responsibility.",
    conjunctive: false,
    bands: [
      { score: 0, label: "Beginning Focus" },
      { score: 1, label: "Emerging Focus" },
      { score: 2, label: "Effective Focus" },
      { score: 3, label: "Highly Effective Focus" },
    ],
  },
  {
    key: "clarify",
    title: "Clarify Priorities",
    description: "The board sets clear goals AND clear guardrails. Both must be well-formed (conjunctive).",
    conjunctive: true,
    sub: [
      { key: "clarify_goals", label: "Goals", hint: "How well-formed are the board's student outcome goals?" },
      { key: "clarify_guardrails", label: "Guardrails", hint: "How well-formed are the board's operational guardrails?" },
    ],
    bands: [
      { score: 0, label: "Beginning Clarity" },
      { score: 1, label: "Emerging Focus" },
      { score: 2, label: "Effective Focus" },
      { score: 3, label: "Highly Effective Focus" },
    ],
  },
  {
    key: "monitor",
    title: "Monitor Progress",
    description: "The board regularly reviews meaningful data on progress toward its goals.",
    conjunctive: false,
    bands: [
      { score: 0, label: "Beginning Monitoring" },
      { score: 1, label: "Emerging Focus" },
      { score: 2, label: "Effective Focus" },
      { score: 3, label: "Highly Effective Focus" },
    ],
  },
  {
    key: "align",
    title: "Align Resources",
    description: "The board ensures budget, staffing, and policy decisions align to student outcome goals.",
    conjunctive: false,
    bands: [
      { score: 0, label: "Beginning Alignment" },
      { score: 1, label: "Emerging Focus" },
      { score: 2, label: "Effective Focus" },
      { score: 3, label: "Highly Effective Focus" },
    ],
  },
  {
    key: "communicate",
    title: "Communicate Results",
    description: "The board communicates clearly and consistently with the community.",
    conjunctive: false,
    bands: [
      { score: 0, label: "Beginning Communication" },
      { score: 1, label: "Emerging Focus" },
      { score: 2, label: "Effective Focus" },
      { score: 3, label: "Highly Effective Focus" },
    ],
  },
] as const;

type ScoreMap = Record<string, number>;

type PracticeScore = { practice: string; raw_band: number; score: number; ceiling: number; band_label: string };
type ClarifyDetail = { goals_band: number; guardrails_band: number; conjunctive_band: number };
type Result = {
  session_id: string;
  district_name: string;
  period_start: string;
  period_end: string;
  total_score: number;
  composite_band: number;
  practice_scores: PracticeScore[];
  clarify_detail: ClarifyDetail | null;
  certified_disclaimer: string;
};

const COMPOSITE_LABELS = ["", "Beginning Focus", "Emerging Focus", "Effective Focus", "Highly Effective Focus"];

export default function CertifiedAssessmentPage() {
  const [stage, setStage] = useState<Stage>("setup");
  const [scores, setScores] = useState<ScoreMap>({});
  const [districtId, setDistrictId] = useState("");
  const [districtName, setDistrictName] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [notes, setNotes] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [districtSearch, setDistrictSearch] = useState("");
  const [districtResults, setDistrictResults] = useState<{ id: string; name: string; state: string }[]>([]);

  function token() { return typeof window !== "undefined" ? sessionStorage.getItem("esb_token") ?? "" : ""; }

  async function searchDistricts(q: string) {
    if (q.length < 2) { setDistrictResults([]); return; }
    const res = await fetch(`${API_BASE}/api/districts/search?q=${encodeURIComponent(q)}`, {
      headers: { Authorization: `Bearer ${token()}` },
    });
    const data = await res.json();
    setDistrictResults(data);
  }

  async function handleSubmit() {
    const allScored = PRACTICES.every((p) =>
      p.conjunctive
        ? scores["clarify_goals"] !== undefined && scores["clarify_guardrails"] !== undefined
        : scores[p.key] !== undefined
    );
    if (!allScored) { setError("Please score all five practices."); return; }
    if (!districtId) { setError("Please select a district."); return; }
    if (!periodStart || !periodEnd) { setError("Please enter the assessment period."); return; }

    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/assessments/certified/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token()}` },
        body: JSON.stringify({
          district_id: districtId,
          period_start: periodStart,
          period_end: periodEnd,
          focus_mindset: scores.focus_mindset ?? 0,
          clarify_goals: scores.clarify_goals ?? 0,
          clarify_guardrails: scores.clarify_guardrails ?? 0,
          monitor: scores.monitor ?? 0,
          align: scores.align ?? 0,
          communicate: scores.communicate ?? 0,
          practitioner_notes: notes,
        }),
      });
      if (!res.ok) throw new Error((await res.json()).detail ?? "Submission failed.");
      setResult(await res.json());
      setStage("results");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Submission failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div style={{ background: "var(--esb-section-dark)", padding: "40px 0 30px", color: "#fff" }}>
        <div className="container mx-auto px-4">
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "8px" }}>
            <h1 style={{ fontFamily: "var(--font-heading)", fontSize: "32px", fontWeight: 700, color: "#fff", margin: 0 }}>
              Certified Assessment
            </h1>
            <span style={{ background: "var(--esb-primary)", color: "#fff", fontSize: "12px", fontWeight: 700, padding: "4px 10px", borderRadius: "4px" }}>
              VALIDATED
            </span>
          </div>
          <p style={{ color: "#aaaaaa", margin: 0 }}>The Great on Their Behalf Index · Practitioner-Administered</p>
        </div>
      </div>

      {/* Certified disclaimer — replaces indicative notice */}
      <div style={{ background: "#e8f5e9", borderBottom: "2px solid #28a745" }}>
        <div className="container mx-auto px-4 py-3">
          <p style={{ margin: 0, fontSize: "14px", color: "#1b5e20" }}>
            <strong>Certified Assessment.</strong> This assessment is administered and validated by a
            credentialed Effective School Boards practitioner. Results may be used in official
            reporting and communications.
          </p>
        </div>
      </div>

      <div className="container mx-auto px-4 py-10" style={{ maxWidth: "860px" }}>
        {error && (
          <div style={{ background: "#fff5f5", border: "1px solid #ed3c0d", borderRadius: "4px", padding: "12px 16px", color: "#ed3c0d", marginBottom: "24px", fontSize: "14px" }}>
            {error}
          </div>
        )}

        {/* Setup stage */}
        {stage === "setup" && (
          <div className="esb-card">
            <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "22px", fontWeight: 700, marginBottom: "24px" }}>
              Assessment Setup
            </h2>

            {/* District picker */}
            <div style={{ marginBottom: "20px" }}>
              <label style={{ display: "block", fontFamily: "var(--font-heading)", fontSize: "14px", fontWeight: 700, marginBottom: "6px" }}>
                District
              </label>
              {districtId ? (
                <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "10px 14px", border: "2px solid var(--esb-primary)", borderRadius: "4px", background: "#f0f9ff" }}>
                  <span style={{ fontWeight: 600 }}>{districtName}</span>
                  <button onClick={() => { setDistrictId(""); setDistrictName(""); }}
                    style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: "var(--esb-muted)", fontSize: "18px" }}>×</button>
                </div>
              ) : (
                <div style={{ position: "relative" }}>
                  <input
                    className="esb-input"
                    placeholder="Search by district name…"
                    value={districtSearch}
                    onChange={(e) => { setDistrictSearch(e.target.value); searchDistricts(e.target.value); }}
                  />
                  {districtResults.length > 0 && (
                    <div style={{ position: "absolute", top: "100%", left: 0, right: 0, background: "#fff", border: "1px solid var(--esb-border)", borderRadius: "4px", zIndex: 10, boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }}>
                      {districtResults.map((d) => (
                        <button key={d.id} onClick={() => { setDistrictId(d.id); setDistrictName(`${d.name} (${d.state})`); setDistrictSearch(""); setDistrictResults([]); }}
                          style={{ display: "block", width: "100%", textAlign: "left", padding: "10px 14px", border: "none", background: "none", cursor: "pointer", borderBottom: "1px solid var(--esb-border)" }}>
                          <strong>{d.name}</strong> <span style={{ color: "var(--esb-muted)", fontSize: "13px" }}>{d.state}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Period */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "20px" }}>
              <div>
                <label style={{ display: "block", fontFamily: "var(--font-heading)", fontSize: "14px", fontWeight: 700, marginBottom: "6px" }}>Period Start</label>
                <input type="date" className="esb-input" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
              </div>
              <div>
                <label style={{ display: "block", fontFamily: "var(--font-heading)", fontSize: "14px", fontWeight: 700, marginBottom: "6px" }}>Period End</label>
                <input type="date" className="esb-input" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
              </div>
            </div>

            {/* Notes */}
            <div style={{ marginBottom: "24px" }}>
              <label style={{ display: "block", fontFamily: "var(--font-heading)", fontSize: "14px", fontWeight: 700, marginBottom: "6px" }}>
                Practitioner Notes <span style={{ fontWeight: 400, color: "var(--esb-muted)" }}>(optional)</span>
              </label>
              <textarea
                className="esb-input"
                rows={4}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Context, methodology notes, observations from the assessment process…"
                style={{ resize: "vertical" }}
              />
            </div>

            <button
              className="btn-primary"
              onClick={() => { if (!districtId || !periodStart || !periodEnd) { setError("District and period are required."); return; } setError(""); setStage("scoring"); }}
              style={{ fontSize: "16px", padding: "12px 40px" }}
            >
              Begin Scoring
            </button>
          </div>
        )}

        {/* Scoring stage */}
        {stage === "scoring" && (
          <div>
            <div className="esb-card" style={{ marginBottom: "20px", background: "var(--esb-light-bg)" }}>
              <div style={{ display: "flex", gap: "32px", fontSize: "14px" }}>
                <span><strong>District:</strong> {districtName}</span>
                <span><strong>Period:</strong> {periodStart} → {periodEnd}</span>
              </div>
            </div>

            {PRACTICES.map((practice, idx) => (
              <div key={practice.key} className="esb-card" style={{ marginBottom: "20px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
                  <div>
                    <span style={{ fontFamily: "var(--font-heading)", fontSize: "12px", fontWeight: 600, color: "var(--esb-muted)", textTransform: "uppercase", letterSpacing: "1px" }}>
                      {idx + 1}/{PRACTICES.length}
                    </span>
                    <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "20px", fontWeight: 700, margin: "4px 0 6px" }}>{practice.title}</h2>
                  </div>
                  {practice.conjunctive && (
                    <span style={{ background: "#e3f2fd", color: "#1976d2", fontSize: "12px", fontWeight: 600, padding: "3px 8px", borderRadius: "4px" }}>Conjunctive</span>
                  )}
                </div>
                <p style={{ color: "var(--esb-text)", fontSize: "14px", marginBottom: "16px" }}>{practice.description}</p>

                {practice.conjunctive ? (
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
                    {practice.sub.map((sub) => (
                      <div key={sub.key}>
                        <p style={{ fontFamily: "var(--font-heading)", fontWeight: 700, fontSize: "15px", marginBottom: "4px" }}>{sub.label}</p>
                        <p style={{ color: "var(--esb-muted)", fontSize: "13px", marginBottom: "10px" }}>{sub.hint}</p>
                        {practice.bands.map((b) => (
                          <BandButton key={b.score} band={b} selected={scores[sub.key] === b.score}
                            onChange={() => setScores((p) => ({ ...p, [sub.key]: b.score }))} name={sub.key} />
                        ))}
                      </div>
                    ))}
                    {scores.clarify_goals !== undefined && scores.clarify_guardrails !== undefined && (
                      <div style={{ gridColumn: "span 2", background: "#e8f5e9", borderRadius: "4px", padding: "10px 14px", fontSize: "13px", color: "#2e7d32" }}>
                        <strong>Conjunctive result: Band {Math.min(scores.clarify_goals, scores.clarify_guardrails)}</strong> (lower of Goals and Guardrails)
                      </div>
                    )}
                  </div>
                ) : (
                  practice.bands.map((b) => (
                    <BandButton key={b.score} band={b} selected={scores[practice.key] === b.score}
                      onChange={() => setScores((p) => ({ ...p, [practice.key]: b.score }))} name={practice.key} />
                  ))
                )}
              </div>
            ))}

            <div style={{ display: "flex", gap: "12px" }}>
              <button className="btn-primary" onClick={handleSubmit} disabled={loading}
                style={{ fontSize: "16px", padding: "12px 40px", opacity: loading ? 0.7 : 1 }}>
                {loading ? "Submitting…" : "Submit Certified Assessment"}
              </button>
              <button onClick={() => setStage("setup")}
                style={{ background: "none", border: "2px solid var(--esb-border)", borderRadius: "4px", padding: "12px 24px", cursor: "pointer", fontFamily: "var(--font-heading)" }}>
                Back to Setup
              </button>
            </div>
          </div>
        )}

        {/* Results stage */}
        {stage === "results" && result && (
          <div>
            <div className="esb-card" style={{ marginBottom: "24px", textAlign: "center" }}>
              <div style={{ display: "inline-flex", width: "120px", height: "120px", borderRadius: "50%", border: "6px solid var(--esb-primary)", alignItems: "center", justifyContent: "center", margin: "0 auto 16px", flexDirection: "column" }}>
                <div style={{ fontSize: "40px", fontWeight: 700, fontFamily: "var(--font-heading)", color: "var(--esb-primary)", lineHeight: 1 }}>{result.total_score}</div>
                <div style={{ fontSize: "13px", color: "var(--esb-muted)" }}>/ 100</div>
              </div>
              <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "28px", fontWeight: 700, margin: "0 0 4px" }}>
                {COMPOSITE_LABELS[result.composite_band]}
              </h2>
              <p style={{ color: "var(--esb-muted)", marginBottom: "16px" }}>
                {result.district_name} · {result.period_start} – {result.period_end}
              </p>
              <div style={{ background: "#e8f5e9", border: "1px solid #28a745", borderRadius: "4px", padding: "10px 16px", fontSize: "13px", color: "#1b5e20", textAlign: "left" }}>
                <strong>Certified Assessment.</strong> {result.certified_disclaimer}
              </div>
            </div>

            <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "20px", fontWeight: 700, marginBottom: "16px" }}>Practice Breakdown</h3>
            {result.practice_scores.map((ps) => (
              <div key={ps.practice} className="esb-card" style={{ marginBottom: "12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <h4 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, margin: "0 0 2px" }}>
                      {PRACTICES.find((p) => p.key === ps.practice)?.title ?? ps.practice}
                    </h4>
                    <span style={{ fontSize: "13px", color: "var(--esb-primary)", fontWeight: 600 }}>{ps.band_label}</span>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: "26px", fontWeight: 700, fontFamily: "var(--font-heading)", color: "var(--esb-dark)" }}>{ps.score}</div>
                    <div style={{ fontSize: "12px", color: "var(--esb-muted)" }}>/ {ps.ceiling}</div>
                  </div>
                </div>
                <div style={{ marginTop: "10px", background: "var(--esb-light-bg)", borderRadius: "4px", height: "6px", overflow: "hidden" }}>
                  <div style={{ width: `${(ps.score / ps.ceiling) * 100}%`, height: "100%", background: "var(--esb-primary)" }} />
                </div>
              </div>
            ))}

            {result.clarify_detail && (
              <div className="esb-card" style={{ marginTop: "8px", marginBottom: "24px", background: "#e3f2fd", fontSize: "13px" }}>
                <strong>Clarify Priorities (conjunctive):</strong> Goals Band {result.clarify_detail.goals_band} · Guardrails Band {result.clarify_detail.guardrails_band} → Conjunctive Band {result.clarify_detail.conjunctive_band}
              </div>
            )}

            <div style={{ display: "flex", gap: "12px" }}>
              <button onClick={() => { setStage("setup"); setScores({}); setResult(null); }} className="btn-outline">
                New Assessment
              </button>
              <a href={`/portal/assessments/${result.session_id}`} className="btn-primary">
                View Full Report
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function BandButton({ band, selected, onChange, name }: {
  band: { score: number; label: string };
  selected: boolean;
  onChange: () => void;
  name: string;
}) {
  return (
    <label style={{
      display: "flex", alignItems: "center", gap: "10px", padding: "10px 14px", marginBottom: "6px",
      border: `2px solid ${selected ? "var(--esb-primary)" : "var(--esb-border)"}`,
      borderRadius: "4px", cursor: "pointer", background: selected ? "#f0f9ff" : "#fff", transition: "all 0.15s",
    }}>
      <input type="radio" name={name} checked={selected} onChange={onChange} style={{ accentColor: "var(--esb-primary)" }} />
      <span style={{ fontFamily: "var(--font-heading)", fontWeight: 700, fontSize: "14px", color: selected ? "var(--esb-primary)" : "var(--esb-dark)" }}>
        Band {band.score}: {band.label}
      </span>
    </label>
  );
}
