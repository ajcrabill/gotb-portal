"use client";

import { API_BASE } from "@/lib/api";

import { useEffect, useState } from "react";

type Client = {
  engagement_id: string;
  district_id: string;
  district_name: string;
  district_state: string;
  is_esb_referral: boolean;
  started_at: string | null;
  ended_at: string | null;
};

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = sessionStorage.getItem("esb_token");
    fetch(`${API_BASE}/api/clients/`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => r.json())
      .then(setClients)
      .catch(() => setError("Failed to load client engagements."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div style={{ background: "var(--esb-section-dark)", padding: "40px 0 30px", color: "#fff" }}>
        <div className="container mx-auto px-4">
          <h1 style={{ fontFamily: "var(--font-heading)", fontSize: "32px", fontWeight: 700, color: "#fff", margin: 0 }}>
            My Clients
          </h1>
          <p style={{ color: "#aaaaaa", marginTop: "8px", marginBottom: 0 }}>Active district engagements</p>
        </div>
      </div>

      <div className="container mx-auto px-4 py-10">
        {loading && <p style={{ color: "var(--esb-muted)" }}>Loading…</p>}
        {error && (
          <div style={{ background: "#fff5f5", border: "1px solid #ed3c0d", borderRadius: "4px", padding: "12px 16px", color: "#ed3c0d", marginBottom: "24px" }}>
            {error}
          </div>
        )}

        {!loading && clients.length === 0 && (
          <div className="esb-card" style={{ textAlign: "center", padding: "60px 30px" }}>
            <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "20px", fontWeight: 700, marginBottom: "12px" }}>
              No active client engagements
            </h3>
            <p style={{ color: "var(--esb-muted)", marginBottom: "24px" }}>
              When Effective School Boards refers a district to you or you add a self-sourced client, they will appear here.
            </p>
            <a href="/referrals" className="btn-primary">View Referrals</a>
          </div>
        )}

        {clients.length > 0 && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: "20px" }}>
            {clients.map((c) => (
              <div key={c.engagement_id} className="esb-card" style={{ position: "relative" }}>
                {c.is_esb_referral && (
                  <span style={{ position: "absolute", top: "16px", right: "16px", background: "var(--esb-primary)", color: "#fff", fontSize: "11px", fontWeight: 700, padding: "3px 8px", borderRadius: "4px", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                    ESB Referral
                  </span>
                )}
                <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "18px", fontWeight: 700, margin: "0 0 4px", paddingRight: "90px" }}>
                  {c.district_name}
                </h3>
                <p style={{ color: "var(--esb-muted)", fontSize: "14px", margin: "0 0 16px" }}>{c.district_state}</p>
                <div style={{ borderTop: "1px solid var(--esb-border)", paddingTop: "14px", display: "flex", justifyContent: "space-between", fontSize: "13px" }}>
                  <span style={{ color: "var(--esb-muted)" }}>
                    Started {c.started_at ? new Date(c.started_at).toLocaleDateString() : "—"}
                  </span>
                  <a href={`/assessments?district=${c.district_id}`} style={{ color: "var(--esb-primary)", fontWeight: 600 }}>
                    View Assessments →
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
