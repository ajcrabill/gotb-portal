"use client";

import { useEffect, useState } from "react";
import { API_BASE, auth, getToken } from "@/lib/api";

type Job = {
  id: string;
  status: string;
  video_url: string;
  district_name: string | null;
  meeting_date: string | null;
  meeting_type: string | null;
  review_span: string;
  result_url: string | null;
  error_msg: string | null;
  meetings_analyzed: number | null;
  created_at: string;
  updated_at: string;
};

type RepoEntry = {
  id: string;
  district_name: string | null;
  meeting_date: string | null;
  meeting_type: string | null;
  result_url: string | null;
  created_at: string;
  submitted_by: string;
};

const REVIEW_SPANS = [
  { value: "1_meeting", label: "Single Meeting" },
  { value: "1_month", label: "1-Month Review" },
  { value: "3_month", label: "3-Month Review" },
  { value: "6_month", label: "6-Month Review" },
];

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  return { Authorization: `Bearer ${getToken() ?? ""}`, ...extra };
}

const PRACTITIONER_ROLES = [
  "certified_practitioner", "senior_practitioner", "practitioner_manager",
  "lead_senior_practitioner", "practitioner_in_training", "superuser",
];

export default function TimeUseEvalPage() {
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [tab, setTab] = useState<"submit" | "jobs" | "repository">("submit");

  useEffect(() => {
    auth.me().then((me) => setAuthorized(me.roles.some((r) => PRACTITIONER_ROLES.includes(r))))
      .catch(() => setAuthorized(false));
  }, []);

  if (authorized === null) return <p style={{ color: "var(--esb-muted)" }}>Loading…</p>;
  if (!authorized) {
    return (
      <div className="esb-card" style={{ textAlign: "center", padding: "60px 30px" }}>
        <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "20px", marginBottom: "8px" }}>Practitioner access required</h3>
        <p style={{ color: "var(--esb-muted)" }}>This tool is available to certified practitioners.</p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ background: "var(--esb-section-dark)", padding: "30px 0", color: "#fff", marginBottom: "24px" }}>
        <div className="container mx-auto px-4">
          <h1 style={{ fontFamily: "var(--font-heading)", fontSize: "28px", fontWeight: 700, color: "#fff", margin: 0 }}>
            Time Use Evaluation
          </h1>
        </div>
      </div>

      <div className="container mx-auto px-4">
        <div style={{ display: "flex", gap: "4px", marginBottom: "24px", borderBottom: "2px solid var(--esb-border)" }}>
          {(["submit", "jobs", "repository"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                padding: "10px 20px", background: "none", border: "none",
                borderBottom: tab === t ? "3px solid var(--esb-primary)" : "3px solid transparent",
                fontFamily: "var(--font-heading)", fontWeight: 600, fontSize: "14px",
                color: tab === t ? "var(--esb-primary)" : "var(--esb-muted)",
                cursor: "pointer", textTransform: "capitalize",
              }}
            >
              {t === "jobs" ? "My Evaluations" : t === "repository" ? "Repository" : "Submit"}
            </button>
          ))}
        </div>

        {tab === "submit" && <SubmitTab onSubmitted={() => setTab("jobs")} />}
        {tab === "jobs" && <JobsTab />}
        {tab === "repository" && <RepositoryTab />}
      </div>
    </div>
  );
}

function SubmitTab({ onSubmitted }: { onSubmitted: () => void }) {
  const [videoUrl, setVideoUrl] = useState("");
  const [district, setDistrict] = useState("");
  const [meetingDate, setMeetingDate] = useState("");
  const [meetingType, setMeetingType] = useState("Regular Board Meeting");
  const [reviewSpan, setReviewSpan] = useState("1_meeting");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    if (!videoUrl) { setError("Please enter a video URL."); return; }
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/eval/submit`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          video_url: videoUrl, district_name: district || null,
          meeting_date: meetingDate || null, meeting_type: meetingType,
          review_span: reviewSpan,
        }),
      });
      if (!res.ok) throw new Error((await res.json()).detail ?? "Submission failed.");
      setVideoUrl(""); setDistrict(""); setMeetingDate("");
      onSubmitted();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Submission failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="esb-card" style={{ maxWidth: "600px" }}>
      {error && <div style={{ background: "#fdecea", border: "1px solid #ed3c0d", borderRadius: "4px", padding: "10px 16px", color: "#ed3c0d", marginBottom: "16px", fontSize: "14px" }}>{error}</div>}

      <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>Video URL</label>
      <input className="esb-input" value={videoUrl} onChange={(e) => setVideoUrl(e.target.value)} placeholder="https://youtube.com/watch?v=…" style={{ marginBottom: "16px" }} />

      <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>District Name</label>
      <input className="esb-input" value={district} onChange={(e) => setDistrict(e.target.value)} style={{ marginBottom: "16px" }} />

      <div style={{ display: "flex", gap: "12px", marginBottom: "16px" }}>
        <div style={{ flex: 1 }}>
          <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>Meeting Date</label>
          <input type="date" className="esb-input" value={meetingDate} onChange={(e) => setMeetingDate(e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>Meeting Type</label>
          <input className="esb-input" value={meetingType} onChange={(e) => setMeetingType(e.target.value)} />
        </div>
      </div>

      <label style={{ display: "block", fontSize: "13px", fontWeight: 600, marginBottom: "6px" }}>Review Span</label>
      <select className="esb-input" value={reviewSpan} onChange={(e) => setReviewSpan(e.target.value)} style={{ marginBottom: "20px" }}>
        {REVIEW_SPANS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
      </select>

      <button className="btn-primary" onClick={submit} disabled={loading} style={{ width: "100%" }}>
        {loading ? "Submitting…" : "Submit for Evaluation"}
      </button>
      <p style={{ fontSize: "12px", color: "var(--esb-muted)", marginTop: "12px" }}>
        Evaluations run in the background — transcription and analysis can take several minutes. Check &quot;My Evaluations&quot; for status.
      </p>
    </div>
  );
}

function JobsTab() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    const res = await fetch(`${API_BASE}/api/eval/jobs`, { headers: authHeaders() });
    if (res.ok) setJobs(await res.json());
    setLoading(false);
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 8000);
    return () => clearInterval(interval);
  }, []);

  async function hide(id: string) {
    await fetch(`${API_BASE}/api/eval/jobs/${id}`, { method: "DELETE", headers: authHeaders() });
    load();
  }

  if (loading) return <p style={{ color: "var(--esb-muted)" }}>Loading…</p>;

  return (
    <div className="esb-card" style={{ padding: 0, overflow: "hidden" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "var(--esb-light-bg)", borderBottom: "2px solid var(--esb-border)" }}>
            {["District", "Date", "Span", "Status", "Submitted", ""].map((h) => (
              <th key={h} style={{ padding: "12px 16px", textAlign: "left", fontFamily: "var(--font-heading)", fontSize: "13px", fontWeight: 700 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {jobs.map((j, i) => (
            <tr key={j.id} style={{ borderBottom: "1px solid var(--esb-border)", background: i % 2 === 0 ? "#fff" : "var(--esb-light-bg)" }}>
              <td style={{ padding: "12px 16px", fontSize: "14px", fontWeight: 600 }}>{j.district_name || "—"}</td>
              <td style={{ padding: "12px 16px", fontSize: "13px", color: "var(--esb-muted)" }}>{j.meeting_date || "—"}</td>
              <td style={{ padding: "12px 16px", fontSize: "13px" }}>{j.review_span.replace("_", " ")}</td>
              <td style={{ padding: "12px 16px" }}>
                <span style={{
                  background: j.status === "complete" ? "#e8f5e9" : j.status === "error" ? "#fdecea" : "#fff3cd",
                  color: j.status === "complete" ? "#1b5e20" : j.status === "error" ? "#ed3c0d" : "#856404",
                  padding: "2px 8px", borderRadius: "4px", fontSize: "12px", fontWeight: 600,
                }}>
                  {j.status}
                </span>
                {j.error_msg && j.status !== "complete" && (
                  <p style={{ fontSize: "11px", color: "var(--esb-muted)", marginTop: "4px", maxWidth: "260px" }}>{j.error_msg.split("\n")[0]}</p>
                )}
              </td>
              <td style={{ padding: "12px 16px", fontSize: "12px", color: "var(--esb-muted)" }}>{new Date(j.created_at).toLocaleString()}</td>
              <td style={{ padding: "12px 16px" }}>
                {j.status === "complete" && j.result_url && (
                  <a href={j.result_url} className="btn-outline" style={{ fontSize: "12px", padding: "5px 12px", marginRight: "6px" }}>Download</a>
                )}
                <button onClick={() => hide(j.id)} style={{ background: "none", border: "none", color: "var(--esb-muted)", cursor: "pointer", fontSize: "12px" }}>Hide</button>
              </td>
            </tr>
          ))}
          {jobs.length === 0 && (
            <tr><td colSpan={6} style={{ padding: "24px", textAlign: "center", color: "var(--esb-muted)" }}>No evaluations yet.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function RepositoryTab() {
  const [items, setItems] = useState<RepoEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/eval/repository`, { headers: authHeaders() })
      .then((r) => r.json()).then(setItems).finally(() => setLoading(false));
  }, []);

  if (loading) return <p style={{ color: "var(--esb-muted)" }}>Loading…</p>;

  return (
    <div className="esb-card" style={{ padding: 0, overflow: "hidden" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "var(--esb-light-bg)", borderBottom: "2px solid var(--esb-border)" }}>
            {["District", "Date", "Type", "Submitted By", "Date Submitted", ""].map((h) => (
              <th key={h} style={{ padding: "12px 16px", textAlign: "left", fontFamily: "var(--font-heading)", fontSize: "13px", fontWeight: 700 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((e, i) => (
            <tr key={e.id} style={{ borderBottom: "1px solid var(--esb-border)", background: i % 2 === 0 ? "#fff" : "var(--esb-light-bg)" }}>
              <td style={{ padding: "12px 16px", fontSize: "14px", fontWeight: 600 }}>{e.district_name || "—"}</td>
              <td style={{ padding: "12px 16px", fontSize: "13px", color: "var(--esb-muted)" }}>{e.meeting_date || "—"}</td>
              <td style={{ padding: "12px 16px", fontSize: "13px" }}>{e.meeting_type || "—"}</td>
              <td style={{ padding: "12px 16px", fontSize: "13px", color: "var(--esb-muted)" }}>{e.submitted_by}</td>
              <td style={{ padding: "12px 16px", fontSize: "12px", color: "var(--esb-muted)" }}>{new Date(e.created_at).toLocaleDateString()}</td>
              <td style={{ padding: "12px 16px" }}>
                {e.result_url && <a href={e.result_url} className="btn-outline" style={{ fontSize: "12px", padding: "5px 12px" }}>Download</a>}
              </td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr><td colSpan={6} style={{ padding: "24px", textAlign: "center", color: "var(--esb-muted)" }}>No completed evaluations yet.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
