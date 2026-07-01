"use client";

import { useEffect, useState } from "react";
import { API_BASE, getToken } from "@/lib/api";

type Tab = "overview" | "districts" | "verifier" | "dossier" | "newsworthy" | "studio" | "leadgen";

const TABS: { key: Tab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "districts", label: "Districts" },
  { key: "verifier", label: "Verifier" },
  { key: "dossier", label: "Dossier Builder" },
  { key: "newsworthy", label: "Newsworthy" },
  { key: "studio", label: "Studio" },
  { key: "leadgen", label: "Lead Generator" },
];

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

export default function CrmPage() {
  const [tab, setTab] = useState<Tab>("overview");

  return (
    <div>
      <div style={{ display: "flex", gap: "4px", marginBottom: "24px", borderBottom: "2px solid var(--esb-border)", flexWrap: "wrap" }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              padding: "10px 20px",
              background: "none",
              border: "none",
              borderBottom: tab === t.key ? "3px solid var(--esb-primary)" : "3px solid transparent",
              fontFamily: "var(--font-heading)",
              fontWeight: 600,
              fontSize: "14px",
              color: tab === t.key ? "var(--esb-primary)" : "var(--esb-muted)",
              cursor: "pointer",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab />}
      {tab === "districts" && <DistrictsTab />}
      {tab === "verifier" && <VerifierTab />}
      {tab === "dossier" && <DossierTab />}
      {tab === "newsworthy" && <NewsworthyTab />}
      {tab === "studio" && <StudioTab />}
      {tab === "leadgen" && <LeadgenTab />}
    </div>
  );
}

// ── shared: district search box ─────────────────────────────────────────────

type DistrictLite = {
  id: string;
  name: string;
  state: string;
  city: string;
  enrollment: number | null;
  band: string;
  cgcs_member: boolean | null;
  website: string;
  people_count: number;
};

function DistrictSearchBox({ onPick }: { onPick: (d: DistrictLite) => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<DistrictLite[]>([]);
  const [loading, setLoading] = useState(false);

  async function search() {
    if (!q.trim()) { setResults([]); return; }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/crm/districts?q=${encodeURIComponent(q)}&page_size=10`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setResults(data.districts ?? []);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div style={{ display: "flex", gap: "8px", marginBottom: "10px" }}>
        <input
          className="esb-input"
          placeholder="Search district by name or city…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          style={{ maxWidth: "360px" }}
        />
        <button className="btn-outline" onClick={search} style={{ fontSize: "13px", padding: "8px 18px" }}>
          {loading ? "Searching…" : "Search"}
        </button>
      </div>
      {results.length > 0 && (
        <div className="esb-card" style={{ padding: "8px", marginBottom: "16px" }}>
          {results.map((d) => (
            <div
              key={d.id}
              onClick={() => { onPick(d); setResults([]); setQ(d.name); }}
              style={{ padding: "8px 10px", cursor: "pointer", borderBottom: "1px solid var(--esb-border)", fontSize: "13px" }}
            >
              <strong>{d.name}</strong> — {d.city}, {d.state} ({d.enrollment ?? "—"} students)
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Tab 1: Overview ──────────────────────────────────────────────────────────

type Stats = {
  districts: number;
  people: number;
  superintendents: number;
  board_members: number;
  former_members: number;
  emails: number;
  by_band: Record<string, number>;
  states: number;
  by_state: Record<string, number>;
  verification: {
    emails_by_status: Record<string, number>;
    site_verified: number;
    districts_crawled: number;
    districts_total: number;
  };
};

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="esb-card" style={{ textAlign: "center" }}>
      <div style={{ fontSize: "28px", fontWeight: 700, color: "var(--esb-primary)" }}>{value}</div>
      <div style={{ fontSize: "13px", color: "var(--esb-muted)", marginTop: "4px" }}>{label}</div>
    </div>
  );
}

function OverviewTab() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/crm/stats`, { headers: authHeaders() });
        if (!res.ok) throw new Error((await res.json()).detail ?? "Failed to load stats.");
        setStats(await res.json());
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load stats.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <p style={{ color: "var(--esb-muted)" }}>Loading…</p>;
  if (error) return errBox(error);
  if (!stats) return null;

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: "12px", marginBottom: "24px" }}>
        <StatCard label="Districts" value={stats.districts} />
        <StatCard label="People" value={stats.people} />
        <StatCard label="Superintendents" value={stats.superintendents} />
        <StatCard label="Board Members" value={stats.board_members} />
        <StatCard label="Former Members" value={stats.former_members} />
        <StatCard label="Emails" value={stats.emails} />
        <StatCard label="States" value={stats.states} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "24px" }}>
        <div className="esb-card">
          <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, marginBottom: "10px" }}>By State</h3>
          <table style={{ width: "100%", fontSize: "13px" }}>
            <tbody>
              {Object.entries(stats.by_state).sort((a, b) => b[1] - a[1]).map(([state, count]) => (
                <tr key={state} style={{ borderBottom: "1px solid var(--esb-border)" }}>
                  <td style={{ padding: "6px 4px" }}>{state || "—"}</td>
                  <td style={{ padding: "6px 4px", textAlign: "right", fontWeight: 600 }}>{count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="esb-card">
          <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, marginBottom: "10px" }}>By Enrollment Band</h3>
          <table style={{ width: "100%", fontSize: "13px" }}>
            <tbody>
              {Object.entries(stats.by_band).sort((a, b) => b[1] - a[1]).map(([band, count]) => (
                <tr key={band} style={{ borderBottom: "1px solid var(--esb-border)" }}>
                  <td style={{ padding: "6px 4px" }}>{band || "—"}</td>
                  <td style={{ padding: "6px 4px", textAlign: "right", fontWeight: 600 }}>{count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="esb-card">
        <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, marginBottom: "10px" }}>Verification</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: "12px", marginBottom: "12px" }}>
          <StatCard label="Site Verified Emails" value={stats.verification.site_verified} />
          <StatCard label="Districts Crawled" value={`${stats.verification.districts_crawled}/${stats.verification.districts_total}`} />
        </div>
        <table style={{ width: "100%", fontSize: "13px" }}>
          <thead>
            <tr><th style={{ textAlign: "left", padding: "6px 4px" }}>Email Status</th><th style={{ textAlign: "right", padding: "6px 4px" }}>Count</th></tr>
          </thead>
          <tbody>
            {Object.entries(stats.verification.emails_by_status).map(([status, count]) => (
              <tr key={status} style={{ borderBottom: "1px solid var(--esb-border)" }}>
                <td style={{ padding: "6px 4px" }}>{status}</td>
                <td style={{ padding: "6px 4px", textAlign: "right", fontWeight: 600 }}>{count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Tab 2: Districts ─────────────────────────────────────────────────────────

type PersonEmail = { email: string; status: string; source: string; last_checked: string | null };
type Person = {
  id: string; role: string; name: string; title: string; status: string;
  subscriber: boolean; last_seen_at: string | null; departed_at: string | null;
  emails: PersonEmail[];
};
type DistrictDetail = DistrictLite & {
  nces_lea_id?: string; zip?: string; street?: string; phone?: string; county?: string;
  district_type?: string; operational_schools?: number; source?: string;
  last_crawled_at?: string | null; last_crawl_note?: string | null;
  people: Person[];
};

function DistrictsTab() {
  const [q, setQ] = useState("");
  const [state, setState] = useState("");
  const [band, setBand] = useState("");
  const [cgcs, setCgcs] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [total, setTotal] = useState(0);
  const [districts, setDistricts] = useState<DistrictLite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<DistrictDetail | null>(null);
  const [sort, setSort] = useState("enrollment");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  function toggleSort(col: string) {
    if (sort === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSort(col);
      setSortDir("desc");
    }
    setPage(1);
  }

  async function load() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (state) params.set("state", state);
      if (band) params.set("band", band);
      if (cgcs) params.set("cgcs", cgcs);
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      params.set("sort", sort);
      params.set("dir", sortDir);
      const res = await fetch(`${API_BASE}/api/crm/districts?${params.toString()}`, { headers: authHeaders() });
      if (!res.ok) throw new Error((await res.json()).detail ?? "Failed to load districts.");
      const data = await res.json();
      setTotal(data.total ?? 0);
      setDistricts(data.districts ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load districts.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [page, sort, sortDir]);

  async function openDistrict(id: string) {
    try {
      const res = await fetch(`${API_BASE}/api/crm/districts/${id}`, { headers: authHeaders() });
      if (!res.ok) throw new Error((await res.json()).detail ?? "Failed to load district.");
      setSelected(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load district.");
    }
  }

  if (selected) {
    return (
      <div className="esb-card">
        <button onClick={() => setSelected(null)} style={{ background: "none", border: "none", color: "var(--esb-primary)", cursor: "pointer", fontSize: "13px", marginBottom: "12px", padding: 0 }}>
          ← Back to districts
        </button>
        <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "20px", fontWeight: 700, margin: 0 }}>{selected.name}</h2>
        <p style={{ color: "var(--esb-muted)", fontSize: "13px", marginTop: "4px", marginBottom: "16px" }}>
          {selected.city}, {selected.state} · {selected.enrollment ?? "—"} students ({selected.band}) · {selected.website || "no website"}
          {selected.cgcs_member ? " · CGCS member" : ""}
        </p>
        <p style={{ fontSize: "12px", color: "var(--esb-muted)", marginBottom: "20px" }}>
          Last crawled: {selected.last_crawled_at ? new Date(selected.last_crawled_at).toLocaleString() : "never"}
          {selected.last_crawl_note ? ` — ${selected.last_crawl_note}` : ""}
        </p>

        <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, marginBottom: "10px" }}>
          People ({selected.people.length})
        </h3>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
            <thead>
              <tr style={{ background: "var(--esb-light-bg)", borderBottom: "2px solid var(--esb-border)" }}>
                {["Name", "Role", "Title", "Status", "Subscriber", "Emails"].map((h) => (
                  <th key={h} style={{ padding: "10px 12px", textAlign: "left", fontFamily: "var(--font-heading)", fontWeight: 700 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {selected.people.map((p, i) => (
                <tr key={p.id} style={{ borderBottom: "1px solid var(--esb-border)", background: i % 2 === 0 ? "#fff" : "var(--esb-light-bg)" }}>
                  <td style={{ padding: "10px 12px", fontWeight: 600 }}>{p.name}</td>
                  <td style={{ padding: "10px 12px" }}>{p.role}</td>
                  <td style={{ padding: "10px 12px", color: "var(--esb-muted)" }}>{p.title}</td>
                  <td style={{ padding: "10px 12px" }}>{p.status}</td>
                  <td style={{ padding: "10px 12px" }}>{p.subscriber ? "✓" : "—"}</td>
                  <td style={{ padding: "10px 12px" }}>
                    {p.emails.length === 0 && "—"}
                    {p.emails.map((e) => (
                      <div key={e.email} style={{ marginBottom: "2px" }}>
                        {e.email} <span style={{
                          color: e.status === "verified" ? "#1b5e20" : "var(--esb-muted)",
                          fontSize: "11px", fontWeight: 600,
                        }}>({e.status})</span>
                      </div>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return (
    <div>
      {error && errBox(error)}
      <div style={{ display: "flex", gap: "8px", marginBottom: "16px", flexWrap: "wrap" }}>
        <input className="esb-input" placeholder="Search name/city…" value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: "220px" }} />
        <input className="esb-input" placeholder="State (e.g. TX)" value={state} onChange={(e) => setState(e.target.value)} style={{ maxWidth: "120px" }} />
        <input className="esb-input" placeholder="Band" value={band} onChange={(e) => setBand(e.target.value)} style={{ maxWidth: "120px" }} />
        <select className="esb-input" value={cgcs} onChange={(e) => setCgcs(e.target.value)} style={{ maxWidth: "160px" }}>
          <option value="">CGCS: any</option>
          <option value="true">CGCS member</option>
          <option value="false">Not CGCS</option>
        </select>
        <button className="btn-primary" onClick={() => { setPage(1); load(); }} style={{ fontSize: "13px", padding: "8px 20px" }}>Filter</button>
      </div>

      {loading ? <p style={{ color: "var(--esb-muted)" }}>Loading…</p> : (
        <>
          <div className="esb-card" style={{ padding: 0, overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "var(--esb-light-bg)", borderBottom: "2px solid var(--esb-border)" }}>
                  {[
                    { label: "Name", key: "name" },
                    { label: "State", key: "state" },
                    { label: "City", key: "city" },
                    { label: "Enrollment", key: "enrollment" },
                    { label: "Band", key: "band" },
                    { label: "CGCS", key: "cgcs_member" },
                    { label: "People", key: null },
                    { label: "", key: null },
                  ].map((h) => (
                    <th
                      key={h.label || "actions"}
                      onClick={h.key ? () => toggleSort(h.key as string) : undefined}
                      style={{
                        padding: "12px 16px", textAlign: "left", fontFamily: "var(--font-heading)",
                        fontSize: "13px", fontWeight: 700, cursor: h.key ? "pointer" : "default",
                        userSelect: "none", whiteSpace: "nowrap",
                      }}
                    >
                      {h.label}
                      {h.key && sort === h.key && (sortDir === "asc" ? " ▲" : " ▼")}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {districts.map((d, i) => (
                  <tr key={d.id} onClick={() => openDistrict(d.id)} style={{ borderBottom: "1px solid var(--esb-border)", background: i % 2 === 0 ? "#fff" : "var(--esb-light-bg)", cursor: "pointer" }}>
                    <td style={{ padding: "12px 16px", fontSize: "14px", fontWeight: 600 }}>{d.name}</td>
                    <td style={{ padding: "12px 16px", fontSize: "13px" }}>{d.state}</td>
                    <td style={{ padding: "12px 16px", fontSize: "13px", color: "var(--esb-muted)" }}>{d.city}</td>
                    <td style={{ padding: "12px 16px", fontSize: "13px" }}>{d.enrollment ?? "—"}</td>
                    <td style={{ padding: "12px 16px", fontSize: "13px" }}>{d.band}</td>
                    <td style={{ padding: "12px 16px", fontSize: "13px" }}>{d.cgcs_member ? "✓" : "—"}</td>
                    <td style={{ padding: "12px 16px", fontSize: "13px" }}>{d.people_count}</td>
                    <td style={{ padding: "12px 16px", fontSize: "13px", color: "var(--esb-primary)" }}>View →</td>
                  </tr>
                ))}
                {districts.length === 0 && (
                  <tr><td colSpan={8} style={{ padding: "24px 16px", textAlign: "center", color: "var(--esb-muted)" }}>No districts found.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "16px" }}>
            <span style={{ fontSize: "13px", color: "var(--esb-muted)" }}>
              {total} total · page {page} of {Math.max(1, Math.ceil(total / pageSize))}
            </span>
            <div style={{ display: "flex", gap: "8px" }}>
              <button className="btn-outline" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} style={{ fontSize: "13px", padding: "6px 16px" }}>Prev</button>
              <button className="btn-outline" disabled={page * pageSize >= total} onClick={() => setPage((p) => p + 1)} style={{ fontSize: "13px", padding: "6px 16px" }}>Next</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ── Tab 3: Verifier ──────────────────────────────────────────────────────────

function VerifierTab() {
  const [stats, setStats] = useState<{ emails_by_status: Record<string, number>; total: number } | null>(null);
  const [picked, setPicked] = useState<DistrictLite | null>(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<unknown>(null);
  const [error, setError] = useState("");

  async function loadStats() {
    const res = await fetch(`${API_BASE}/api/crm/verifier/stats`, { headers: authHeaders() });
    if (res.ok) setStats(await res.json());
  }

  useEffect(() => { loadStats(); }, []);

  async function runVerify() {
    if (!picked) return;
    setRunning(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/crm/verifier/district/${picked.id}`, { method: "POST", headers: authHeaders() });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Verify failed.");
      setResult(data);
      loadStats();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Verify failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      {stats && (
        <div className="esb-card" style={{ marginBottom: "20px" }}>
          <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, marginBottom: "10px" }}>Verification Stats</h3>
          <p style={{ fontSize: "13px", marginBottom: "8px" }}>Total emails: <strong>{stats.total}</strong></p>
          <table style={{ width: "100%", fontSize: "13px" }}>
            <tbody>
              {Object.entries(stats.emails_by_status).map(([status, count]) => (
                <tr key={status} style={{ borderBottom: "1px solid var(--esb-border)" }}>
                  <td style={{ padding: "6px 4px" }}>{status}</td>
                  <td style={{ padding: "6px 4px", textAlign: "right", fontWeight: 600 }}>{count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="esb-card">
        <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, marginBottom: "10px" }}>Verify a District</h3>
        <DistrictSearchBox onPick={setPicked} />
        {picked && (
          <div style={{ marginBottom: "16px" }}>
            <p style={{ fontSize: "13px" }}>Selected: <strong>{picked.name}</strong> ({picked.city}, {picked.state})</p>
            <button className="btn-primary" disabled={running} onClick={runVerify} style={{ fontSize: "13px", padding: "8px 20px", marginTop: "8px" }}>
              {running ? "Crawling + verifying… this can take a while" : "Verify District"}
            </button>
          </div>
        )}
        {error && errBox(error)}
        {result != null && (
          <pre style={{ background: "var(--esb-light-bg)", padding: "16px", borderRadius: "4px", fontSize: "12px", overflowX: "auto", whiteSpace: "pre-wrap" }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}

// ── Tab 4: Dossier Builder ───────────────────────────────────────────────────

type Claim = { field: string; value: string; confidence: number | string; source_url: string; source_tier: string; verdict: string };
type SearchRow = { method: string; source: string; query: string; url: string; found: boolean };
type Dossier = { id: string; subject: string; status: string; summary: string; claims: Claim[]; searches: SearchRow[] };

function DossierTab() {
  const [status, setStatus] = useState<{ llm_configured: boolean; model: string } | null>(null);
  const [district, setDistrict] = useState<DistrictDetail | null>(null);
  const [districtLite, setDistrictLite] = useState<DistrictLite | null>(null);
  const [personId, setPersonId] = useState("");
  const [subjectName, setSubjectName] = useState("");
  const [building, setBuilding] = useState(false);
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/api/crm/dossier/status`, { headers: authHeaders() })
      .then((r) => r.json()).then(setStatus).catch(() => {});
  }, []);

  async function pickDistrict(d: DistrictLite) {
    setDistrictLite(d);
    setPersonId("");
    try {
      const res = await fetch(`${API_BASE}/api/crm/districts/${d.id}`, { headers: authHeaders() });
      if (res.ok) setDistrict(await res.json());
    } catch {
      // ignore
    }
  }

  async function build() {
    setBuilding(true);
    setError("");
    setDossier(null);
    try {
      const body: Record<string, string> = {};
      if (personId) body.person_id = personId;
      else if (districtLite) body.district_id = districtLite.id;
      else if (subjectName) body.subject_name = subjectName;
      else { setError("Pick a district/person, or enter a subject name."); setBuilding(false); return; }

      const res = await fetch(`${API_BASE}/api/crm/dossier/build`, {
        method: "POST", headers: authHeaders({ "Content-Type": "application/json" }), body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Build failed.");
      setDossier(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Build failed.");
    } finally {
      setBuilding(false);
    }
  }

  return (
    <div>
      {status && (
        <p style={{ fontSize: "12px", color: "var(--esb-muted)", marginBottom: "16px" }}>
          LLM: {status.llm_configured ? `configured (${status.model})` : "not configured"}
        </p>
      )}

      <div className="esb-card" style={{ marginBottom: "20px" }}>
        <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, marginBottom: "10px" }}>Build a Dossier</h3>
        <DistrictSearchBox onPick={pickDistrict} />

        {district && (
          <div style={{ marginBottom: "16px" }}>
            <label style={{ fontSize: "13px", fontWeight: 600, display: "block", marginBottom: "6px" }}>
              Person (optional — leave blank to build for the district)
            </label>
            <select className="esb-input" value={personId} onChange={(e) => setPersonId(e.target.value)} style={{ maxWidth: "360px" }}>
              <option value="">(district-level dossier)</option>
              {district.people.map((p) => (
                <option key={p.id} value={p.id}>{p.name} — {p.role}</option>
              ))}
            </select>
          </div>
        )}

        <div style={{ marginBottom: "16px" }}>
          <label style={{ fontSize: "13px", fontWeight: 600, display: "block", marginBottom: "6px" }}>
            Or free-text subject name
          </label>
          <input className="esb-input" placeholder="e.g. Jane Doe, Superintendent" value={subjectName} onChange={(e) => setSubjectName(e.target.value)} style={{ maxWidth: "360px" }} />
        </div>

        <button className="btn-primary" disabled={building} onClick={build} style={{ fontSize: "13px", padding: "8px 20px" }}>
          {building ? "Building…" : "Build Dossier"}
        </button>
        {error && <div style={{ marginTop: "12px" }}>{errBox(error)}</div>}
      </div>

      {dossier && (
        <div className="esb-card">
          <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "18px", fontWeight: 700, marginBottom: "6px" }}>{dossier.subject}</h3>
          <p style={{ fontSize: "12px", color: "var(--esb-muted)", marginBottom: "16px" }}>Status: {dossier.status}</p>
          {dossier.summary && (
            <p style={{ fontSize: "14px", lineHeight: "1.6", marginBottom: "20px", whiteSpace: "pre-wrap" }}>{dossier.summary}</p>
          )}

          <h4 style={{ fontFamily: "var(--font-heading)", fontSize: "15px", fontWeight: 700, marginBottom: "10px" }}>Claims ({dossier.claims.length})</h4>
          <div style={{ overflowX: "auto", marginBottom: "20px" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
              <thead>
                <tr style={{ background: "var(--esb-light-bg)", borderBottom: "2px solid var(--esb-border)" }}>
                  {["Field", "Value", "Confidence", "Source", "Tier", "Verdict"].map((h) => (
                    <th key={h} style={{ padding: "8px 10px", textAlign: "left", fontFamily: "var(--font-heading)", fontWeight: 700 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dossier.claims.map((c, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid var(--esb-border)" }}>
                    <td style={{ padding: "8px 10px", fontWeight: 600 }}>{c.field}</td>
                    <td style={{ padding: "8px 10px" }}>{c.value}</td>
                    <td style={{ padding: "8px 10px" }}>{c.confidence}</td>
                    <td style={{ padding: "8px 10px" }}>
                      {c.source_url ? <a href={c.source_url} target="_blank" rel="noopener noreferrer">link</a> : "—"}
                    </td>
                    <td style={{ padding: "8px 10px" }}>{c.source_tier}</td>
                    <td style={{ padding: "8px 10px" }}>{c.verdict}</td>
                  </tr>
                ))}
                {dossier.claims.length === 0 && (
                  <tr><td colSpan={6} style={{ padding: "16px", textAlign: "center", color: "var(--esb-muted)" }}>No claims.</td></tr>
                )}
              </tbody>
            </table>
          </div>

          <h4 style={{ fontFamily: "var(--font-heading)", fontSize: "15px", fontWeight: 700, marginBottom: "10px" }}>Searches ({dossier.searches.length})</h4>
          <ul style={{ fontSize: "13px", paddingLeft: "18px" }}>
            {dossier.searches.map((s, i) => (
              <li key={i} style={{ marginBottom: "4px" }}>
                [{s.method}/{s.source}] {s.query} — {s.found ? "found" : "not found"} {s.url && <a href={s.url} target="_blank" rel="noopener noreferrer">(link)</a>}
              </li>
            ))}
            {dossier.searches.length === 0 && <li style={{ color: "var(--esb-muted)" }}>No searches recorded.</li>}
          </ul>
        </div>
      )}
    </div>
  );
}

// ── Tab 5: Newsworthy ────────────────────────────────────────────────────────

type Signal = {
  id: string; district: string; state: string; district_id: string; kind: string;
  severity: string; headline: string; snippet: string; url: string; matched_terms: string[]; status: string;
};

function NewsworthyTab() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [stats, setStats] = useState<{ by_severity: Record<string, number>; total: number; districts_flagged: number } | null>(null);
  const [severity, setSeverity] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<unknown>(null);

  async function loadSignals() {
    const params = new URLSearchParams();
    if (severity) params.set("severity", severity);
    if (status) params.set("status", status);
    params.set("limit", "50");
    const res = await fetch(`${API_BASE}/api/crm/newsworthy/signals?${params.toString()}`, { headers: authHeaders() });
    if (res.ok) setSignals((await res.json()).signals ?? []);
  }

  async function loadStats() {
    const res = await fetch(`${API_BASE}/api/crm/newsworthy/stats`, { headers: authHeaders() });
    if (res.ok) setStats(await res.json());
  }

  useEffect(() => { loadSignals(); loadStats(); }, [severity, status]);

  async function scan(d: DistrictLite) {
    setScanning(true);
    setScanResult(null);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/crm/newsworthy/scan/${d.id}`, { method: "POST", headers: authHeaders() });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Scan failed.");
      setScanResult(data);
      loadSignals(); loadStats();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Scan failed.");
    } finally {
      setScanning(false);
    }
  }

  const sevColor = (s: string) => (s === "high" ? "#ed3c0d" : s === "medium" ? "#e0a800" : "var(--esb-muted)");

  return (
    <div>
      {stats && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: "12px", marginBottom: "20px" }}>
          <StatCard label="Total Signals" value={stats.total} />
          <StatCard label="Districts Flagged" value={stats.districts_flagged} />
          {Object.entries(stats.by_severity).map(([sev, count]) => (
            <StatCard key={sev} label={`Severity: ${sev}`} value={count} />
          ))}
        </div>
      )}

      <div className="esb-card" style={{ marginBottom: "20px" }}>
        <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, marginBottom: "10px" }}>Scan a District</h3>
        <DistrictSearchBox onPick={scan} />
        {scanning && <p style={{ fontSize: "13px", color: "var(--esb-muted)" }}>Scanning…</p>}
        {error && errBox(error)}
        {scanResult != null && (
          <pre style={{ background: "var(--esb-light-bg)", padding: "12px", borderRadius: "4px", fontSize: "12px", whiteSpace: "pre-wrap" }}>
            {JSON.stringify(scanResult, null, 2)}
          </pre>
        )}
      </div>

      <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
        <select className="esb-input" value={severity} onChange={(e) => setSeverity(e.target.value)} style={{ maxWidth: "160px" }}>
          <option value="">Severity: any</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <select className="esb-input" value={status} onChange={(e) => setStatus(e.target.value)} style={{ maxWidth: "160px" }}>
          <option value="">Status: any</option>
          <option value="new">New</option>
          <option value="contacted">Contacted</option>
          <option value="dismissed">Dismissed</option>
        </select>
      </div>

      <div className="esb-card" style={{ padding: 0, overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "var(--esb-light-bg)", borderBottom: "2px solid var(--esb-border)" }}>
              {["District", "State", "Kind", "Severity", "Headline", "Status", ""].map((h) => (
                <th key={h} style={{ padding: "10px 12px", textAlign: "left", fontFamily: "var(--font-heading)", fontSize: "13px", fontWeight: 700 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {signals.map((s, i) => (
              <tr key={s.id} style={{ borderBottom: "1px solid var(--esb-border)", background: i % 2 === 0 ? "#fff" : "var(--esb-light-bg)" }}>
                <td style={{ padding: "10px 12px", fontSize: "13px", fontWeight: 600 }}>{s.district}</td>
                <td style={{ padding: "10px 12px", fontSize: "13px" }}>{s.state}</td>
                <td style={{ padding: "10px 12px", fontSize: "13px" }}>{s.kind}</td>
                <td style={{ padding: "10px 12px", fontSize: "13px", fontWeight: 700, color: sevColor(s.severity) }}>{s.severity}</td>
                <td style={{ padding: "10px 12px", fontSize: "13px" }}>{s.headline}</td>
                <td style={{ padding: "10px 12px", fontSize: "13px" }}>{s.status}</td>
                <td style={{ padding: "10px 12px", fontSize: "13px" }}>
                  {s.url && <a href={s.url} target="_blank" rel="noopener noreferrer">link</a>}
                </td>
              </tr>
            ))}
            {signals.length === 0 && (
              <tr><td colSpan={7} style={{ padding: "20px 12px", textAlign: "center", color: "var(--esb-muted)" }}>No signals.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Tab 6: Studio ─────────────────────────────────────────────────────────────

function StudioTab() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
      <GovernanceWriter />
      <PresentationCreator />
    </div>
  );
}

function GovernanceWriter() {
  const [purpose, setPurpose] = useState("");
  const [context, setContext] = useState("");
  const [draft, setDraft] = useState("");
  const [writing, setWriting] = useState(false);
  const [writeResult, setWriteResult] = useState<unknown>(null);
  const [lintText, setLintText] = useState("");
  const [linting, setLinting] = useState(false);
  const [flags, setFlags] = useState<unknown[] | null>(null);
  const [error, setError] = useState("");

  async function write() {
    setWriting(true);
    setError("");
    setWriteResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/crm/studio/governance/write`, {
        method: "POST", headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ purpose, context, draft }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Write failed.");
      setWriteResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Write failed.");
    } finally {
      setWriting(false);
    }
  }

  async function lint() {
    setLinting(true);
    setError("");
    setFlags(null);
    try {
      const res = await fetch(`${API_BASE}/api/crm/studio/governance/lint`, {
        method: "POST", headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ text: lintText }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Lint failed.");
      setFlags(data.voice_flags ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Lint failed.");
    } finally {
      setLinting(false);
    }
  }

  return (
    <div className="esb-card">
      <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, marginBottom: "12px" }}>Governance Writer</h3>
      {error && errBox(error)}
      <input className="esb-input" placeholder="Purpose" value={purpose} onChange={(e) => setPurpose(e.target.value)} style={{ marginBottom: "10px" }} />
      <textarea className="esb-input" placeholder="Context" value={context} onChange={(e) => setContext(e.target.value)} style={{ minHeight: "80px", marginBottom: "10px" }} />
      <textarea className="esb-input" placeholder="Draft" value={draft} onChange={(e) => setDraft(e.target.value)} style={{ minHeight: "80px", marginBottom: "10px" }} />
      <button className="btn-primary" disabled={writing} onClick={write} style={{ fontSize: "13px", padding: "8px 20px", marginBottom: "16px" }}>
        {writing ? "Writing…" : "Write"}
      </button>
      {writeResult != null && (
        <pre style={{ background: "var(--esb-light-bg)", padding: "12px", borderRadius: "4px", fontSize: "12px", whiteSpace: "pre-wrap", marginBottom: "20px" }}>
          {typeof writeResult === "string" ? writeResult : JSON.stringify(writeResult, null, 2)}
        </pre>
      )}

      <hr style={{ border: "none", borderTop: "1px solid var(--esb-border)", margin: "16px 0" }} />
      <h4 style={{ fontFamily: "var(--font-heading)", fontSize: "14px", fontWeight: 700, marginBottom: "10px" }}>Lint Existing Text</h4>
      <textarea className="esb-input" placeholder="Text to lint" value={lintText} onChange={(e) => setLintText(e.target.value)} style={{ minHeight: "80px", marginBottom: "10px" }} />
      <button className="btn-outline" disabled={linting} onClick={lint} style={{ fontSize: "13px", padding: "8px 20px" }}>
        {linting ? "Linting…" : "Lint"}
      </button>
      {flags != null && (
        <ul style={{ fontSize: "13px", marginTop: "12px", paddingLeft: "18px" }}>
          {flags.map((f, i) => (
            <li key={i}>{typeof f === "string" ? f : JSON.stringify(f)}</li>
          ))}
          {flags.length === 0 && <li style={{ color: "var(--esb-muted)" }}>No flags.</li>}
        </ul>
      )}
    </div>
  );
}

function PresentationCreator() {
  const [topic, setTopic] = useState("");
  const [outlining, setOutlining] = useState(false);
  const [outline, setOutline] = useState<{ title?: string; subtitle?: string; slides?: unknown[] } | null>(null);
  const [outlineText, setOutlineText] = useState("");
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState("");

  async function getOutline() {
    setOutlining(true);
    setError("");
    setOutline(null);
    try {
      const res = await fetch(`${API_BASE}/api/crm/studio/presentation/outline`, {
        method: "POST", headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ topic }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Outline failed.");
      setOutline(data);
      setOutlineText(JSON.stringify(data, null, 2));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Outline failed.");
    } finally {
      setOutlining(false);
    }
  }

  async function buildDeck() {
    setBuilding(true);
    setError("");
    try {
      let spec: { title: string; subtitle?: string; slides?: unknown[] };
      try {
        spec = JSON.parse(outlineText);
      } catch {
        throw new Error("Outline JSON is invalid — fix it before building.");
      }
      if (!spec.title) spec.title = topic || "ESB Deck";

      const res = await fetch(`${API_BASE}/api/crm/studio/presentation/build`, {
        method: "POST", headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(spec),
      });
      if (!res.ok) {
        let msg = "Build failed.";
        try { msg = (await res.json()).detail ?? msg; } catch {}
        throw new Error(msg);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "esb-deck.pptx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Build failed.");
    } finally {
      setBuilding(false);
    }
  }

  return (
    <div className="esb-card">
      <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, marginBottom: "12px" }}>Presentation Creator</h3>
      {error && errBox(error)}
      <input className="esb-input" placeholder="Topic" value={topic} onChange={(e) => setTopic(e.target.value)} style={{ marginBottom: "10px" }} />
      <button className="btn-outline" disabled={outlining} onClick={getOutline} style={{ fontSize: "13px", padding: "8px 20px", marginBottom: "16px" }}>
        {outlining ? "Generating outline…" : "Generate Outline"}
      </button>

      {outline != null && (
        <div style={{ marginBottom: "16px" }}>
          <label style={{ fontSize: "13px", fontWeight: 600, display: "block", marginBottom: "6px" }}>
            Outline (editable — must be {"{title, subtitle, slides}"} shape before building)
          </label>
          <textarea
            className="esb-input"
            value={outlineText}
            onChange={(e) => setOutlineText(e.target.value)}
            style={{ minHeight: "220px", fontFamily: "monospace", fontSize: "12px" }}
          />
        </div>
      )}

      <button className="btn-primary" disabled={building || !outlineText} onClick={buildDeck} style={{ fontSize: "13px", padding: "8px 20px" }}>
        {building ? "Building deck…" : "Build Deck"}
      </button>
    </div>
  );
}

// ── Tab 7: Lead Generator ────────────────────────────────────────────────────

type Campaign = { id: string; name: string; status: string; messages: number; daily_cap: number };
type QueueDraft = {
  id: string; to: string; name: string; role: string; district: string; state: string;
  subject: string; body: string; rationale: string; touch: number; sequence_id: string | null;
};

function LeadgenTab() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [newCampaign, setNewCampaign] = useState({ name: "", subject: "", template: "", daily_cap: 40 });
  const [suppression, setSuppression] = useState<{ suppressed: number; send_ready: boolean } | null>(null);
  const [queue, setQueue] = useState<{ pending: number; drafts: QueueDraft[]; send_ready: boolean; postal_address_set: boolean } | null>(null);
  const [error, setError] = useState("");
  const [genCount, setGenCount] = useState(5);
  const [generating, setGenerating] = useState(false);
  const [declineFor, setDeclineFor] = useState<QueueDraft | null>(null);
  const [declineReason, setDeclineReason] = useState("");
  const [declineIntent, setDeclineIntent] = useState<"training" | "instruction">("training");

  async function loadCampaigns() {
    const res = await fetch(`${API_BASE}/api/crm/leadgen/campaigns`, { headers: authHeaders() });
    if (res.ok) setCampaigns((await res.json()).campaigns ?? []);
  }
  async function loadSuppression() {
    const res = await fetch(`${API_BASE}/api/crm/leadgen/suppression`, { headers: authHeaders() });
    if (res.ok) setSuppression(await res.json());
  }
  async function loadQueue() {
    const res = await fetch(`${API_BASE}/api/crm/leadgen/queue?limit=25`, { headers: authHeaders() });
    if (res.ok) setQueue(await res.json());
  }

  useEffect(() => { loadCampaigns(); loadSuppression(); loadQueue(); }, []);

  async function createCampaign() {
    if (!newCampaign.name) return;
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/crm/leadgen/campaigns`, {
        method: "POST", headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ name: newCampaign.name, segment: {}, subject: newCampaign.subject, template: newCampaign.template, daily_cap: newCampaign.daily_cap }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Failed to create campaign.");
      setNewCampaign({ name: "", subject: "", template: "", daily_cap: 40 });
      loadCampaigns();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create campaign.");
    }
  }

  async function buildCampaign(cid: string) {
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/crm/leadgen/campaigns/${cid}/build`, { method: "POST", headers: authHeaders() });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Build failed.");
      loadCampaigns();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Build failed.");
    }
  }

  async function generateDrafts() {
    setGenerating(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/crm/leadgen/generate?count=${genCount}`, { method: "POST", headers: authHeaders() });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Generate failed.");
      loadQueue();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Generate failed.");
    } finally {
      setGenerating(false);
    }
  }

  async function approve(mid: string) {
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/crm/leadgen/${mid}/approve`, { method: "POST", headers: authHeaders() });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Approve failed.");
      if (data.blocked) setError(data.reason ?? "Blocked.");
      loadQueue();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Approve failed.");
    }
  }

  function startDecline(d: QueueDraft) {
    setDeclineFor(d);
    setDeclineReason("");
    setDeclineIntent("training");
  }

  async function submitDecline() {
    if (!declineFor) return;
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/crm/leadgen/${declineFor.id}/decline`, {
        method: "POST", headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ reason: declineReason, intent: declineIntent }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Decline failed.");
      setDeclineFor(null);
      loadQueue();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Decline failed.");
    }
  }

  return (
    <div>
      {error && errBox(error)}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: "12px", marginBottom: "20px" }}>
        {suppression && (
          <>
            <StatCard label="Suppressed" value={suppression.suppressed} />
            <StatCard label="Send Ready" value={suppression.send_ready ? "Yes" : "No (no postal address)"} />
          </>
        )}
        {queue && <StatCard label="Pending Drafts" value={queue.pending} />}
      </div>

      {/* Campaigns */}
      <div className="esb-card" style={{ marginBottom: "20px" }}>
        <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, marginBottom: "12px" }}>Campaigns</h3>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "16px" }}>
          <input className="esb-input" placeholder="Name" value={newCampaign.name} onChange={(e) => setNewCampaign({ ...newCampaign, name: e.target.value })} style={{ maxWidth: "180px" }} />
          <input className="esb-input" placeholder="Subject" value={newCampaign.subject} onChange={(e) => setNewCampaign({ ...newCampaign, subject: e.target.value })} style={{ maxWidth: "220px" }} />
          <input className="esb-input" placeholder="Template" value={newCampaign.template} onChange={(e) => setNewCampaign({ ...newCampaign, template: e.target.value })} style={{ maxWidth: "220px" }} />
          <input className="esb-input" type="number" placeholder="Daily cap" value={newCampaign.daily_cap} onChange={(e) => setNewCampaign({ ...newCampaign, daily_cap: Number(e.target.value) })} style={{ maxWidth: "120px" }} />
          <button className="btn-primary" onClick={createCampaign} style={{ fontSize: "13px", padding: "8px 20px" }}>+ Create</button>
        </div>

        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
          <thead>
            <tr style={{ background: "var(--esb-light-bg)", borderBottom: "2px solid var(--esb-border)" }}>
              {["Name", "Status", "Messages", "Daily Cap", ""].map((h) => (
                <th key={h} style={{ padding: "8px 10px", textAlign: "left", fontFamily: "var(--font-heading)", fontWeight: 700 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {campaigns.map((c) => (
              <tr key={c.id} style={{ borderBottom: "1px solid var(--esb-border)" }}>
                <td style={{ padding: "8px 10px", fontWeight: 600 }}>{c.name}</td>
                <td style={{ padding: "8px 10px" }}>{c.status}</td>
                <td style={{ padding: "8px 10px" }}>{c.messages}</td>
                <td style={{ padding: "8px 10px" }}>{c.daily_cap}</td>
                <td style={{ padding: "8px 10px" }}>
                  <button className="btn-outline" onClick={() => buildCampaign(c.id)} style={{ fontSize: "12px", padding: "4px 12px" }}>Build</button>
                </td>
              </tr>
            ))}
            {campaigns.length === 0 && (
              <tr><td colSpan={5} style={{ padding: "16px", textAlign: "center", color: "var(--esb-muted)" }}>No campaigns yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Generate */}
      <div className="esb-card" style={{ marginBottom: "20px" }}>
        <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 700, marginBottom: "12px" }}>Generate New Drafts</h3>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <input className="esb-input" type="number" value={genCount} onChange={(e) => setGenCount(Number(e.target.value))} style={{ maxWidth: "100px" }} />
          <button className="btn-primary" disabled={generating} onClick={generateDrafts} style={{ fontSize: "13px", padding: "8px 20px" }}>
            {generating ? "Generating…" : `Generate ${genCount} New Drafts`}
          </button>
        </div>
      </div>

      {/* Approval queue */}
      <div className="esb-card">
        <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "18px", fontWeight: 700, marginBottom: "6px" }}>Approval Queue</h3>
        <p style={{ fontSize: "12px", color: "var(--esb-muted)", marginBottom: "16px" }}>
          {queue?.postal_address_set ? "Send-ready (postal address configured)." : "NOT send-ready — ESB_POSTAL_ADDRESS is not configured server-side. Approvals will be blocked until it is."}
        </p>

        {queue?.drafts.map((d) => (
          <div key={d.id} style={{ border: "1px solid var(--esb-border)", borderRadius: "4px", padding: "16px", marginBottom: "12px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
              <div>
                <strong>{d.name || d.to}</strong> {d.role && `— ${d.role}`}
                <div style={{ fontSize: "12px", color: "var(--esb-muted)" }}>{d.district} {d.state && `(${d.state})`} · touch {d.touch}</div>
              </div>
              <div style={{ display: "flex", gap: "8px" }}>
                <button className="btn-primary" onClick={() => approve(d.id)} style={{ fontSize: "12px", padding: "6px 14px" }}>Approve</button>
                <button onClick={() => startDecline(d)} style={{ background: "#ed3c0d", color: "#fff", border: "none", borderRadius: "4px", padding: "6px 14px", fontSize: "12px", cursor: "pointer" }}>Decline</button>
              </div>
            </div>
            <p style={{ fontSize: "13px", marginBottom: "4px" }}><strong>To:</strong> {d.to}</p>
            <p style={{ fontSize: "13px", marginBottom: "4px" }}><strong>Subject:</strong> {d.subject}</p>
            <p style={{ fontSize: "13px", whiteSpace: "pre-wrap", background: "var(--esb-light-bg)", padding: "10px", borderRadius: "4px", marginBottom: "6px" }}>{d.body}</p>
            {d.rationale && <p style={{ fontSize: "12px", color: "var(--esb-muted)" }}><strong>Rationale:</strong> {d.rationale}</p>}

            {declineFor?.id === d.id && (
              <div style={{ marginTop: "10px", padding: "12px", background: "#fff3cd", borderRadius: "4px" }}>
                <textarea
                  className="esb-input"
                  placeholder="Reason for declining…"
                  value={declineReason}
                  onChange={(e) => setDeclineReason(e.target.value)}
                  style={{ minHeight: "60px", marginBottom: "8px" }}
                />
                <div style={{ display: "flex", gap: "16px", marginBottom: "10px", fontSize: "13px" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                    <input type="radio" checked={declineIntent === "training"} onChange={() => setDeclineIntent("training")} />
                    One-off (training signal only)
                  </label>
                  <label style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                    <input type="radio" checked={declineIntent === "instruction"} onChange={() => setDeclineIntent("instruction")} />
                    Standing instruction (applies to future generation)
                  </label>
                </div>
                <div style={{ display: "flex", gap: "8px" }}>
                  <button className="btn-primary" onClick={submitDecline} style={{ fontSize: "12px", padding: "6px 16px" }}>Submit Decline</button>
                  <button onClick={() => setDeclineFor(null)} style={{ background: "none", border: "1px solid var(--esb-border)", borderRadius: "4px", padding: "6px 16px", fontSize: "12px", cursor: "pointer" }}>Cancel</button>
                </div>
              </div>
            )}
          </div>
        ))}
        {queue && queue.drafts.length === 0 && (
          <p style={{ color: "var(--esb-muted)", fontSize: "13px" }}>No drafts pending approval.</p>
        )}
      </div>
    </div>
  );
}
