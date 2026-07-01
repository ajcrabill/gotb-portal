"use client";

import { API_BASE } from "@/lib/api";

import { useEffect, useState } from "react";

type Referral = {
  referral_id: string;
  district_id: string;
  district_name: string;
  district_state: string;
  status: string;
  recommendation_rationale: string | null;
};

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending:   { label: "Pending Review", color: "#ffc107" },
  assigned:  { label: "Assigned",       color: "var(--esb-primary)" },
  accepted:  { label: "Accepted",       color: "#28a745" },
  declined:  { label: "Declined",       color: "#dc3545" },
  rerouted:  { label: "Rerouted",       color: "#6c757d" },
};

export default function ReferralsPage() {
  const [referrals, setReferrals] = useState<Referral[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = sessionStorage.getItem("esb_token");
    fetch(`${API_BASE}/api/clients/referrals`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => r.json())
      .then(setReferrals)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div style={{ background: "var(--esb-section-dark)", padding: "40px 0 30px", color: "#fff" }}>
        <div className="container mx-auto px-4">
          <h1 style={{ fontFamily: "var(--font-heading)", fontSize: "32px", fontWeight: 700, color: "#fff", margin: 0 }}>
            Referrals
          </h1>
          <p style={{ color: "#aaaaaa", marginTop: "8px", marginBottom: 0 }}>
            Districts referred to you by Effective School Boards
          </p>
        </div>
      </div>

      <div className="container mx-auto px-4 py-10">
        {loading && <p style={{ color: "var(--esb-muted)" }}>Loading…</p>}

        {!loading && referrals.length === 0 && (
          <div className="esb-card" style={{ textAlign: "center", padding: "60px 30px" }}>
            <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "20px", fontWeight: 700, marginBottom: "12px" }}>
              No pending referrals
            </h3>
            <p style={{ color: "var(--esb-muted)" }}>
              When Effective School Boards refers a district to you, it will appear here for your review.
            </p>
          </div>
        )}

        {referrals.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            {referrals.map((r) => {
              const statusMeta = STATUS_LABELS[r.status] ?? { label: r.status, color: "var(--esb-muted)" };
              return (
                <div key={r.referral_id} className="esb-card">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div>
                      <h3 style={{ fontFamily: "var(--font-heading)", fontSize: "18px", fontWeight: 700, margin: "0 0 4px" }}>
                        {r.district_name}
                      </h3>
                      <p style={{ color: "var(--esb-muted)", fontSize: "14px", margin: 0 }}>{r.district_state}</p>
                    </div>
                    <span style={{ background: statusMeta.color, color: "#fff", fontSize: "12px", fontWeight: 700, padding: "4px 10px", borderRadius: "4px", whiteSpace: "nowrap" }}>
                      {statusMeta.label}
                    </span>
                  </div>
                  {r.recommendation_rationale && (
                    <p style={{ marginTop: "14px", fontSize: "14px", color: "var(--esb-text)", lineHeight: "1.6", borderTop: "1px solid var(--esb-border)", paddingTop: "14px" }}>
                      <strong>ESB note:</strong> {r.recommendation_rationale}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
