"use client";

import { useState } from "react";
import { API_BASE, getToken } from "@/lib/api";

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  return { Authorization: `Bearer ${getToken() ?? ""}`, ...extra };
}

function errBox(msg: string) {
  return (
    <div style={{ background: "#fdecea", border: "1px solid #ed3c0d", borderRadius: "4px", padding: "10px 16px", color: "#ed3c0d", marginBottom: "16px", fontSize: "14px" }}>
      {msg}
    </div>
  );
}

type Question = { id: string; question: string };

type Citation = { url: string; text: string };
type Initiative = { title: string; statement: string; description: string; citations: Citation[] };
type InterimItem = { title: string; statement: string; initiatives: Initiative[] };
type SmartGoal = { title: string; statement: string; interim_goals: InterimItem[] };
type Guardrail = { title: string; statement: string; interim_guardrails: InterimItem[] };
type Plan = { smart_goal: SmartGoal; guardrails: Guardrail[] };

type Rating = "good" | "flag" | null;

type Annotation = {
  element_id: string;
  element_type: string;
  title: string;
  statement: string;
  rating: "good" | "flag";
  rewrite: string;
  note: string;
};

const PHASE_LABELS: Record<string, string> = {
  started: "Starting…",
  skeleton: "Skeleton drafted…",
  research: "Research gathered…",
  done: "Done!",
};

export default function PlanPage() {
  const [step, setStep] = useState<1 | 2>(1);
  const [outcome, setOutcome] = useState("");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [analyzing, setAnalyzing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [phase, setPhase] = useState<string>("");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [planId, setPlanId] = useState<string>("");
  const [error, setError] = useState("");

  // ratings keyed by a stable element_id
  const [ratings, setRatings] = useState<Record<string, Rating>>({});
  const [rewrites, setRewrites] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [feedbackStatus, setFeedbackStatus] = useState("");

  async function analyze() {
    if (!outcome.trim()) return;
    setAnalyzing(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/plan/analyze`, {
        method: "POST", headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ outcome }),
      });
      if (res.status === 403) {
        setError("You are not currently eligible for the Strategic Plan Generator. If you believe this is an error, contact your practitioner.");
        return;
      }
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Analyze failed.");
      setQuestions(data.questions ?? []);
      setStep(2);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Analyze failed.");
    } finally {
      setAnalyzing(false);
    }
  }

  async function generate() {
    setGenerating(true);
    setError("");
    setPlan(null);
    setPhase("started");
    try {
      const res = await fetch(`${API_BASE}/api/plan/generate`, {
        method: "POST", headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ outcome, answers }),
      });
      if (res.status === 403) {
        setError("You are not currently eligible for the Strategic Plan Generator. If you believe this is an error, contact your practitioner.");
        setGenerating(false);
        return;
      }
      if (!res.ok || !res.body) {
        let msg = "Generate failed.";
        try { msg = (await res.json()).detail ?? msg; } catch {}
        throw new Error(msg);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n\n");
        buffer = lines.pop() ?? "";

        for (const chunk of lines) {
          const line = chunk.trim();
          if (!line || line.startsWith(":")) continue;
          if (!line.startsWith("data:")) continue;
          const jsonStr = line.slice(5).trim();
          try {
            const evt = JSON.parse(jsonStr);
            if (evt.phase) setPhase(evt.phase);
            if (evt.error) {
              setError(evt.error);
            }
            if (evt.done && evt.plan) {
              setPlan(evt.plan);
              setPlanId(crypto.randomUUID());
              setPhase("done");
            }
          } catch {
            // ignore malformed lines
          }
        }
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Generate failed.");
    } finally {
      setGenerating(false);
    }
  }

  function setRating(id: string, r: Rating) {
    setRatings((prev) => ({ ...prev, [id]: r }));
  }

  function ratingControl(id: string, type: string, title: string, statement: string) {
    const r = ratings[id];
    return (
      <div style={{ marginTop: "10px" }}>
        <div style={{ display: "flex", gap: "10px" }}>
          <button
            onClick={() => setRating(id, r === "good" ? null : "good")}
            style={{
              fontSize: "12px", padding: "4px 12px", borderRadius: "4px", cursor: "pointer",
              border: "1px solid var(--esb-border)",
              background: r === "good" ? "#e8f5e9" : "#fff",
              color: r === "good" ? "#1b5e20" : "var(--esb-text)",
            }}
          >
            👍 Good
          </button>
          <button
            onClick={() => setRating(id, r === "flag" ? null : "flag")}
            style={{
              fontSize: "12px", padding: "4px 12px", borderRadius: "4px", cursor: "pointer",
              border: "1px solid var(--esb-border)",
              background: r === "flag" ? "#fdecea" : "#fff",
              color: r === "flag" ? "#ed3c0d" : "var(--esb-text)",
            }}
          >
            🚩 Flag
          </button>
        </div>
        {r === "flag" && (
          <div style={{ marginTop: "8px" }}>
            <textarea
              className="esb-input"
              placeholder="Suggested rewrite…"
              value={rewrites[id] ?? ""}
              onChange={(e) => setRewrites((prev) => ({ ...prev, [id]: e.target.value }))}
              style={{ minHeight: "50px", fontSize: "13px", marginBottom: "6px" }}
            />
            <input
              className="esb-input"
              placeholder="Note (optional)"
              value={notes[id] ?? ""}
              onChange={(e) => setNotes((prev) => ({ ...prev, [id]: e.target.value }))}
              style={{ fontSize: "13px" }}
            />
          </div>
        )}
        {/* hidden data used at submit time */}
        <input type="hidden" data-type={type} data-title={title} data-statement={statement} />
      </div>
    );
  }

  async function submitFeedback() {
    if (!plan) return;
    const annotations: Annotation[] = [];
    for (const [id, rating] of Object.entries(ratings)) {
      if (!rating) continue;
      const [type, ...rest] = id.split(":");
      const title = rest.join(":");
      annotations.push({
        element_id: id,
        element_type: type,
        title,
        statement: "",
        rating,
        rewrite: rewrites[id] ?? "",
        note: notes[id] ?? "",
      });
    }
    if (annotations.length === 0) {
      setFeedbackStatus("No ratings selected yet.");
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/plan/feedback`, {
        method: "POST", headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ plan_id: planId, outcome, annotations }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Failed to save feedback.");
      setFeedbackStatus(`Saved ${data.saved} annotations (${data.good} good, ${data.flagged} flagged).`);
    } catch (e: unknown) {
      setFeedbackStatus(e instanceof Error ? e.message : "Failed to save feedback.");
    }
  }

  function initiativeCard(init: Initiative, keyPrefix: string) {
    const id = `initiative:${keyPrefix}:${init.title}`;
    return (
      <div key={id} style={{ background: "var(--esb-light-bg)", borderRadius: "4px", padding: "12px 14px", marginBottom: "10px" }}>
        <strong style={{ fontSize: "13px" }}>{init.title}</strong>
        <p style={{ fontSize: "13px", margin: "6px 0" }}>{init.statement}</p>
        {init.description && <p style={{ fontSize: "12px", color: "var(--esb-muted)", margin: "6px 0" }}>{init.description}</p>}
        {init.citations?.length > 0 && (
          <ul style={{ fontSize: "12px", paddingLeft: "18px" }}>
            {init.citations.map((c, i) => (
              <li key={i}><a href={c.url} target="_blank" rel="noopener noreferrer">{c.text || c.url}</a></li>
            ))}
          </ul>
        )}
        {ratingControl(id, "initiative", init.title, init.statement)}
      </div>
    );
  }

  function interimCard(item: InterimItem, keyPrefix: string, elementType: string) {
    const id = `${elementType}:${keyPrefix}:${item.title}`;
    return (
      <div key={id} style={{ border: "1px solid var(--esb-border)", borderRadius: "4px", padding: "14px", marginBottom: "14px" }}>
        <h4 style={{ fontFamily: "var(--font-heading)", fontSize: "14px", fontWeight: 700, margin: "0 0 4px" }}>{item.title}</h4>
        <p style={{ fontSize: "13px", margin: "0 0 10px" }}>{item.statement}</p>
        {ratingControl(id, elementType, item.title, item.statement)}
        {item.initiatives?.length > 0 && (
          <div style={{ marginTop: "12px" }}>
            {item.initiatives.map((init) => initiativeCard(init, `${keyPrefix}/${item.title}`))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      {error && errBox(error)}

      {step === 1 && (
        <div className="esb-card">
          <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "18px", fontWeight: 700, marginBottom: "10px" }}>
            Step 1 — Describe the Desired Outcome
          </h3>
          <textarea
            className="esb-input"
            placeholder="e.g. Increase 3rd grade reading proficiency…"
            value={outcome}
            onChange={(e) => setOutcome(e.target.value)}
            style={{ minHeight: "120px", marginBottom: "16px" }}
          />
          <button className="btn-primary" disabled={analyzing || !outcome.trim()} onClick={analyze} style={{ fontSize: "14px", padding: "10px 24px" }}>
            {analyzing ? "Analyzing…" : "Analyze"}
          </button>
        </div>
      )}

      {step === 2 && !plan && (
        <div className="esb-card">
          <button onClick={() => setStep(1)} style={{ background: "none", border: "none", color: "var(--esb-primary)", cursor: "pointer", fontSize: "13px", marginBottom: "12px", padding: 0 }}>
            ← Back
          </button>
          <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "18px", fontWeight: 700, marginBottom: "10px" }}>
            Step 2 — Clarifying Questions
          </h3>
          {questions.length === 0 && (
            <p style={{ fontSize: "13px", color: "var(--esb-muted)", marginBottom: "16px" }}>
              Your outcome already looks complete — no clarifying questions needed.
            </p>
          )}
          {questions.map((q) => (
            <div key={q.id} style={{ marginBottom: "12px" }}>
              <label style={{ fontSize: "13px", fontWeight: 600, display: "block", marginBottom: "6px" }}>{q.question}</label>
              <input
                className="esb-input"
                value={answers[q.id] ?? ""}
                onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
              />
            </div>
          ))}

          <button className="btn-primary" disabled={generating} onClick={generate} style={{ fontSize: "14px", padding: "10px 24px", marginTop: "12px" }}>
            {generating ? "Generating…" : "Generate Plan"}
          </button>

          {generating && (
            <p style={{ marginTop: "16px", fontSize: "14px", color: "var(--esb-primary)", fontWeight: 600 }}>
              {PHASE_LABELS[phase] ?? "Working…"}
            </p>
          )}
        </div>
      )}

      {plan && (
        <div>
          <div className="esb-card" style={{ marginBottom: "20px" }}>
            <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "22px", fontWeight: 700, marginBottom: "6px" }}>SMART Goal</h2>
            <h3 style={{ fontSize: "16px", fontWeight: 700, marginBottom: "6px" }}>{plan.smart_goal.title}</h3>
            <p style={{ fontSize: "14px", marginBottom: "10px" }}>{plan.smart_goal.statement}</p>
            {ratingControl("smart_goal:root", "smart_goal", plan.smart_goal.title, plan.smart_goal.statement)}

            <h4 style={{ fontFamily: "var(--font-heading)", fontSize: "15px", fontWeight: 700, margin: "20px 0 10px" }}>Interim Goals</h4>
            {plan.smart_goal.interim_goals.map((ig) => interimCard(ig, "goal", "interim_goal"))}
          </div>

          {plan.guardrails.map((g, gi) => (
            <div key={gi} className="esb-card" style={{ marginBottom: "20px" }}>
              <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "20px", fontWeight: 700, marginBottom: "6px" }}>Guardrail {gi + 1}</h2>
              <h3 style={{ fontSize: "16px", fontWeight: 700, marginBottom: "6px" }}>{g.title}</h3>
              <p style={{ fontSize: "14px", marginBottom: "10px" }}>{g.statement}</p>
              {ratingControl(`guardrail:${gi}`, "guardrail", g.title, g.statement)}

              <h4 style={{ fontFamily: "var(--font-heading)", fontSize: "15px", fontWeight: 700, margin: "20px 0 10px" }}>Interim Guardrails</h4>
              {g.interim_guardrails.map((igr) => interimCard(igr, `guardrail-${gi}`, "interim_guardrail"))}
            </div>
          ))}

          <div className="esb-card">
            <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, marginBottom: "10px" }}>Submit Feedback</h3>
            <p style={{ fontSize: "13px", color: "var(--esb-muted)", marginBottom: "12px" }}>
              Rate any elements above with 👍 or 🚩, then submit. Flagged items with rewrites help improve future plan generations.
            </p>
            <button className="btn-primary" onClick={submitFeedback} style={{ fontSize: "14px", padding: "10px 24px" }}>
              Submit Feedback
            </button>
            {feedbackStatus && <p style={{ fontSize: "13px", marginTop: "10px", color: "var(--esb-primary)" }}>{feedbackStatus}</p>}
          </div>
        </div>
      )}
    </div>
  );
}
