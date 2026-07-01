"use client";

import { useEffect, useState } from "react";
import { API_BASE, getToken } from "@/lib/api";

type Tab = "drafts" | "sites" | "guides" | "newsletters" | "weights";

type Draft = {
  id: string;
  site_id: string;
  title: string;
  slug: string;
  html_content: string;
  status: string;
  quality_score: number | null;
  quality_notes: string | null;
  created_at: number;
  published_at: number | null;
  human_reviewed: number;
  reviewer_notes: string;
  site_name?: string;
  site_domain?: string;
};

type Site = {
  id: string;
  name: string;
  domain: string;
  repo: string;
  cadence: string;
  posts_dir: string;
  lm_research: string;
  lm_write: string;
  enabled: number;
  last_run: number | null;
  seeds: string;
};

type Guide = { id: string; name: string; has_guide: boolean };

type Newsletter = {
  id: string;
  source: string;
  title: string;
  content_html: string;
  status: string;
  created_at: number;
  beehiiv_post_id: string | null;
};

type Weight = {
  criterion_key: string;
  criterion_name: string;
  weight: number;
  max_raw: number;
  display_order: number;
};

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  return { Authorization: `Bearer ${getToken() ?? ""}`, ...extra };
}

function fmtDate(epoch: number | null): string {
  return epoch ? new Date(epoch * 1000).toLocaleString() : "—";
}

export default function ContentPage() {
  const [tab, setTab] = useState<Tab>("drafts");

  return (
    <div>
      <div style={{ display: "flex", gap: "4px", marginBottom: "24px", borderBottom: "2px solid var(--esb-border)" }}>
        {(["drafts", "sites", "guides", "newsletters", "weights"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: "10px 20px",
              background: "none",
              border: "none",
              borderBottom: tab === t ? "3px solid var(--esb-primary)" : "3px solid transparent",
              fontFamily: "var(--font-heading)",
              fontWeight: 600,
              fontSize: "14px",
              color: tab === t ? "var(--esb-primary)" : "var(--esb-muted)",
              cursor: "pointer",
              textTransform: "capitalize",
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "drafts" && <DraftsTab />}
      {tab === "sites" && <SitesTab />}
      {tab === "guides" && <GuidesTab />}
      {tab === "newsletters" && <NewslettersTab />}
      {tab === "weights" && <WeightsTab />}
    </div>
  );
}

// ── Drafts ───────────────────────────────────────────────────────────────────

function DraftsTab() {
  const [status, setStatus] = useState("pending");
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [selected, setSelected] = useState<Draft | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editedHtml, setEditedHtml] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/content/drafts?status=${status}`, { headers: authHeaders() });
      if (!res.ok) throw new Error((await res.json()).detail ?? "Failed to load drafts.");
      setDrafts(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load drafts.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [status]);

  function openDraft(d: Draft) {
    setSelected(d);
    setEditedHtml(d.html_content);
  }

  async function saveEdits() {
    if (!selected) return;
    const res = await fetch(`${API_BASE}/api/content/draft/${selected.id}`, {
      method: "PUT",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ html_content: editedHtml }),
    });
    if (res.ok) { setSelected({ ...selected, html_content: editedHtml }); load(); }
  }

  async function doAction(action: "approve" | "reject" | "rescind") {
    if (!selected) return;
    const res = await fetch(`${API_BASE}/api/content/draft/${selected.id}/${action}`, {
      method: "POST", headers: authHeaders(),
    });
    if (res.ok) { setSelected(null); load(); }
    else setError((await res.json()).detail ?? `Failed to ${action}.`);
  }

  async function saveNotes(notes: string) {
    if (!selected) return;
    await fetch(`${API_BASE}/api/content/draft/${selected.id}/reviewer-notes`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ notes }),
    });
  }

  async function toggleReviewed() {
    if (!selected) return;
    const reviewed = !selected.human_reviewed;
    await fetch(`${API_BASE}/api/content/draft/${selected.id}/mark-reviewed`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ reviewed }),
    });
    setSelected({ ...selected, human_reviewed: reviewed ? 1 : 0 });
  }

  if (selected) {
    return (
      <div className="esb-card">
        <button
          onClick={() => setSelected(null)}
          style={{ background: "none", border: "none", color: "var(--esb-primary)", cursor: "pointer", fontSize: "13px", marginBottom: "12px", padding: 0 }}
        >
          ← Back to drafts
        </button>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
          <div>
            <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "20px", fontWeight: 700, margin: 0 }}>{selected.title}</h2>
            <p style={{ color: "var(--esb-muted)", fontSize: "13px", marginTop: "4px" }}>
              {selected.site_name} ({selected.site_domain}) · {selected.slug} · created {fmtDate(selected.created_at)}
            </p>
          </div>
          {selected.quality_score !== null && (
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: "22px", fontWeight: 700, color: "var(--esb-primary)" }}>
                {Math.round(selected.quality_score * 100)}%
              </div>
              <div style={{ fontSize: "12px", color: "var(--esb-muted)" }}>quality score</div>
            </div>
          )}
        </div>

        {selected.quality_notes && (
          <div style={{ background: "#fff3cd", border: "1px solid #ffc107", borderRadius: "4px", padding: "10px 14px", marginBottom: "16px", fontSize: "13px" }}>
            {selected.quality_notes}
          </div>
        )}

        <textarea
          className="esb-input"
          value={editedHtml}
          onChange={(e) => setEditedHtml(e.target.value)}
          style={{ width: "100%", minHeight: "320px", fontFamily: "monospace", fontSize: "13px", marginBottom: "12px" }}
        />
        <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
          <button className="btn-outline" onClick={saveEdits}>Save Edits</button>
          <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px" }}>
            <input type="checkbox" checked={!!selected.human_reviewed} onChange={toggleReviewed} />
            Human reviewed
          </label>
        </div>

        <textarea
          className="esb-input"
          placeholder="Reviewer notes…"
          defaultValue={selected.reviewer_notes}
          onBlur={(e) => saveNotes(e.target.value)}
          style={{ width: "100%", minHeight: "70px", fontSize: "13px", marginBottom: "20px" }}
        />

        <div style={{ display: "flex", gap: "10px" }}>
          {selected.status === "pending" && (
            <>
              <button className="btn-primary" onClick={() => doAction("approve")}>Approve & Publish</button>
              <button onClick={() => doAction("reject")} style={{ background: "#ed3c0d", color: "#fff", border: "none", borderRadius: "4px", padding: "10px 20px", cursor: "pointer" }}>
                Reject
              </button>
            </>
          )}
          {selected.status === "published" && (
            <button onClick={() => doAction("rescind")} style={{ background: "#ed3c0d", color: "#fff", border: "none", borderRadius: "4px", padding: "10px 20px", cursor: "pointer" }}>
              Rescind (remove from live site)
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
        {["pending", "published", "rejected"].map((s) => (
          <button
            key={s}
            onClick={() => setStatus(s)}
            className={status === s ? "btn-primary" : "btn-outline"}
            style={{ fontSize: "13px", padding: "6px 16px", textTransform: "capitalize" }}
          >
            {s}
          </button>
        ))}
      </div>
      {error && <div style={{ background: "#fdecea", border: "1px solid #ed3c0d", borderRadius: "4px", padding: "10px 16px", color: "#ed3c0d", marginBottom: "16px", fontSize: "14px" }}>{error}</div>}
      {loading ? <p style={{ color: "var(--esb-muted)" }}>Loading…</p> : (
        <div className="esb-card" style={{ padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "var(--esb-light-bg)", borderBottom: "2px solid var(--esb-border)" }}>
                {["Title", "Site", "Quality", "Reviewed", "Created", ""].map((h) => (
                  <th key={h} style={{ padding: "12px 16px", textAlign: "left", fontFamily: "var(--font-heading)", fontSize: "13px", fontWeight: 700 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {drafts.map((d, i) => (
                <tr key={d.id} onClick={() => openDraft(d)} style={{ borderBottom: "1px solid var(--esb-border)", background: i % 2 === 0 ? "#fff" : "var(--esb-light-bg)", cursor: "pointer" }}>
                  <td style={{ padding: "12px 16px", fontSize: "14px", fontWeight: 600 }}>{d.title}</td>
                  <td style={{ padding: "12px 16px", fontSize: "13px", color: "var(--esb-muted)" }}>{d.site_name}</td>
                  <td style={{ padding: "12px 16px", fontSize: "13px" }}>{d.quality_score !== null ? `${Math.round(d.quality_score * 100)}%` : "—"}</td>
                  <td style={{ padding: "12px 16px", fontSize: "13px" }}>{d.human_reviewed ? "✓" : "—"}</td>
                  <td style={{ padding: "12px 16px", fontSize: "13px", color: "var(--esb-muted)" }}>{fmtDate(d.created_at)}</td>
                  <td style={{ padding: "12px 16px", fontSize: "13px", color: "var(--esb-primary)" }}>Review →</td>
                </tr>
              ))}
              {drafts.length === 0 && (
                <tr><td colSpan={6} style={{ padding: "24px 16px", textAlign: "center", color: "var(--esb-muted)" }}>No {status} drafts.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Sites ────────────────────────────────────────────────────────────────────

function SitesTab() {
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    const res = await fetch(`${API_BASE}/api/content/sites`, { headers: authHeaders() });
    if (res.ok) setSites(await res.json());
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function toggleEnabled(site: Site) {
    const res = await fetch(`${API_BASE}/api/content/sites/${site.id}`, {
      method: "PUT",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        lm_research: site.lm_research, lm_write: site.lm_write,
        cadence: site.cadence, enabled: site.enabled ? 0 : 1,
        seeds: JSON.parse(site.seeds || "[]"),
      }),
    });
    if (res.ok) load();
  }

  async function trigger(siteId: string) {
    setTriggering(siteId);
    await fetch(`${API_BASE}/api/content/sites/${siteId}/trigger`, { method: "POST", headers: authHeaders() });
    setTimeout(() => setTriggering(null), 3000);
  }

  if (loading) return <p style={{ color: "var(--esb-muted)" }}>Loading…</p>;

  return (
    <div className="esb-card" style={{ padding: 0, overflow: "hidden" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "var(--esb-light-bg)", borderBottom: "2px solid var(--esb-border)" }}>
            {["Site", "Domain", "Cadence", "Enabled", "Last Run", ""].map((h) => (
              <th key={h} style={{ padding: "12px 16px", textAlign: "left", fontFamily: "var(--font-heading)", fontSize: "13px", fontWeight: 700 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sites.map((s, i) => (
            <tr key={s.id} style={{ borderBottom: "1px solid var(--esb-border)", background: i % 2 === 0 ? "#fff" : "var(--esb-light-bg)" }}>
              <td style={{ padding: "12px 16px", fontSize: "14px", fontWeight: 600 }}>{s.name}</td>
              <td style={{ padding: "12px 16px", fontSize: "13px", color: "var(--esb-muted)" }}>{s.domain}</td>
              <td style={{ padding: "12px 16px", fontSize: "13px" }}>{s.cadence}</td>
              <td style={{ padding: "12px 16px" }}>
                <input type="checkbox" checked={!!s.enabled} onChange={() => toggleEnabled(s)} />
              </td>
              <td style={{ padding: "12px 16px", fontSize: "13px", color: "var(--esb-muted)" }}>{fmtDate(s.last_run)}</td>
              <td style={{ padding: "12px 16px" }}>
                <button className="btn-outline" disabled={triggering === s.id} onClick={() => trigger(s.id)} style={{ fontSize: "13px", padding: "5px 12px" }}>
                  {triggering === s.id ? "Triggered…" : "Trigger Now"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Guides ───────────────────────────────────────────────────────────────────

function GuidesTab() {
  const [guides, setGuides] = useState<Guide[]>([]);
  const [content, setContent] = useState<{ id: string; text: string } | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/content/guides`, { headers: authHeaders() })
      .then((r) => r.json()).then(setGuides);
  }, []);

  async function open(id: string) {
    const res = await fetch(`${API_BASE}/api/content/guide/${id}`, { headers: authHeaders() });
    if (res.ok) {
      const data = await res.json();
      setContent({ id, text: data.content });
    }
  }

  if (content) {
    return (
      <div className="esb-card">
        <button onClick={() => setContent(null)} style={{ background: "none", border: "none", color: "var(--esb-primary)", cursor: "pointer", fontSize: "13px", marginBottom: "12px", padding: 0 }}>
          ← Back to guides
        </button>
        <pre style={{ whiteSpace: "pre-wrap", fontSize: "13px", lineHeight: "1.6", fontFamily: "monospace" }}>{content.text}</pre>
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "12px" }}>
      {guides.map((g) => (
        <button key={g.id} onClick={() => open(g.id)} className="esb-card" style={{ textAlign: "left", cursor: "pointer", border: "none" }}>
          <strong style={{ fontSize: "14px" }}>{g.name}</strong>
        </button>
      ))}
    </div>
  );
}

// ── Newsletters ──────────────────────────────────────────────────────────────

function NewslettersTab() {
  const [status, setStatus] = useState("pending");
  const [items, setItems] = useState<Newsletter[]>([]);
  const [error, setError] = useState("");

  async function load() {
    const res = await fetch(`${API_BASE}/api/content/newsletters?status=${status}`, { headers: authHeaders() });
    if (res.ok) setItems(await res.json());
  }

  useEffect(() => { load(); }, [status]);

  async function doAction(id: string, action: "approve" | "reject") {
    const res = await fetch(`${API_BASE}/api/content/newsletter/${id}/${action}`, { method: "POST", headers: authHeaders() });
    if (res.ok) load();
    else setError((await res.json()).detail ?? `Failed to ${action}.`);
  }

  return (
    <div>
      <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
        {["pending", "uploaded", "rejected"].map((s) => (
          <button key={s} onClick={() => setStatus(s)} className={status === s ? "btn-primary" : "btn-outline"} style={{ fontSize: "13px", padding: "6px 16px", textTransform: "capitalize" }}>
            {s}
          </button>
        ))}
      </div>
      {error && <div style={{ background: "#fdecea", border: "1px solid #ed3c0d", borderRadius: "4px", padding: "10px 16px", color: "#ed3c0d", marginBottom: "16px", fontSize: "14px" }}>{error}</div>}
      {items.map((n) => (
        <div key={n.id} className="esb-card" style={{ marginBottom: "12px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <strong>{n.title}</strong>
              <p style={{ color: "var(--esb-muted)", fontSize: "13px", margin: "4px 0 0" }}>{fmtDate(n.created_at)} · {n.source}</p>
            </div>
            {n.status === "pending" && (
              <div style={{ display: "flex", gap: "8px" }}>
                <button className="btn-primary" style={{ fontSize: "13px", padding: "6px 14px" }} onClick={() => doAction(n.id, "approve")}>Upload to Beehiiv</button>
                <button onClick={() => doAction(n.id, "reject")} style={{ background: "#ed3c0d", color: "#fff", border: "none", borderRadius: "4px", padding: "6px 14px", fontSize: "13px", cursor: "pointer" }}>Reject</button>
              </div>
            )}
          </div>
        </div>
      ))}
      {items.length === 0 && <p style={{ color: "var(--esb-muted)" }}>No {status} newsletters.</p>}
    </div>
  );
}

// ── Weights (legacy coaching rubric) ────────────────────────────────────────

function WeightsTab() {
  const [weights, setWeights] = useState<Weight[]>([]);
  const [error, setError] = useState("");

  async function load() {
    const res = await fetch(`${API_BASE}/api/content/weights`, { headers: authHeaders() });
    if (res.ok) setWeights(await res.json());
  }

  useEffect(() => { load(); }, []);

  async function updateWeight(key: string, value: number) {
    const res = await fetch(`${API_BASE}/api/content/weights/${key}`, {
      method: "PUT",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ weight: value }),
    });
    if (res.ok) load();
    else setError((await res.json()).detail ?? "Failed to update weight.");
  }

  const total = weights.reduce((sum, w) => sum + w.weight, 0);

  return (
    <div>
      <p style={{ color: "var(--esb-muted)", fontSize: "13px", marginBottom: "16px" }}>
        Legacy coaching-criteria rubric weights (distinct from the portal&apos;s live assessment scoring config).
      </p>
      {error && <div style={{ background: "#fdecea", border: "1px solid #ed3c0d", borderRadius: "4px", padding: "10px 16px", color: "#ed3c0d", marginBottom: "16px", fontSize: "14px" }}>{error}</div>}
      <div className="esb-card">
        {weights.sort((a, b) => a.display_order - b.display_order).map((w) => (
          <div key={w.criterion_key} style={{ display: "flex", alignItems: "center", gap: "16px", marginBottom: "12px" }}>
            <span style={{ width: "220px", fontSize: "14px", fontWeight: 600 }}>{w.criterion_name}</span>
            <input
              type="number" min={0} max={100}
              defaultValue={w.weight}
              onBlur={(e) => updateWeight(w.criterion_key, Number(e.target.value))}
              className="esb-input"
              style={{ width: "90px" }}
            />
            <span style={{ fontSize: "13px", color: "var(--esb-muted)" }}>%</span>
          </div>
        ))}
        <p style={{ fontSize: "13px", fontWeight: 700, color: total === 100 ? "#1b5e20" : "#ed3c0d", marginTop: "12px" }}>
          Total: {total}% {total !== 100 && "(must equal 100%)"}
        </p>
      </div>
    </div>
  );
}
