"use client";

import { API_BASE } from "@/lib/api";

import { useEffect, useState } from "react";

type BillingStatus = {
  has_membership: boolean;
  membership_status: string | null;
  membership_until: string | null;
  has_certification: boolean;
  certification_status: string | null;
  certification_expires: string | null;
};

export default function MembershipPage() {
  const [status, setStatus] = useState<BillingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState("");

  function token() { return sessionStorage.getItem("esb_token") ?? ""; }

  useEffect(() => {
    fetch(`${API_BASE}/api/billing/status`, { headers: { Authorization: `Bearer ${token()}` } })
      .then((r) => r.json())
      .then(setStatus)
      .finally(() => setLoading(false));
  }, []);

  async function startCheckout(product: "membership" | "certification") {
    setActionLoading(product);
    try {
      const res = await fetch(`${API_BASE}/api/billing/${product}/checkout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token()}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Failed.");
      window.location.href = data.checkout_url;
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setActionLoading("");
    }
  }

  async function startConnect() {
    setActionLoading("connect");
    try {
      const res = await fetch(`${API_BASE}/api/billing/connect/onboard`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token()}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Failed.");
      window.location.href = data.onboarding_url;
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setActionLoading("");
    }
  }

  return (
    <div>
      <div style={{ background: "var(--esb-section-dark)", padding: "40px 0 30px", color: "#fff" }}>
        <div className="container mx-auto px-4">
          <h1 style={{ fontFamily: "var(--font-heading)", fontSize: "32px", fontWeight: 700, color: "#fff", margin: 0 }}>
            Membership & Certification
          </h1>
          <p style={{ color: "#aaaaaa", marginTop: "8px", marginBottom: 0 }}>
            Effective School Boards Practitioner Network
          </p>
        </div>
      </div>

      <div className="container mx-auto px-4 py-10" style={{ maxWidth: "900px" }}>
        {loading ? (
          <p style={{ color: "var(--esb-muted)" }}>Loading…</p>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "24px" }}>
            {/* Membership */}
            <div className="esb-card" style={{ display: "flex", flexDirection: "column" }}>
              <div style={{ marginBottom: "16px" }}>
                <span style={{ fontFamily: "var(--font-heading)", fontSize: "12px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "1px", color: "var(--esb-muted)" }}>Annual Membership</span>
                <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "36px", fontWeight: 700, margin: "8px 0 4px" }}>$2,500</h2>
                <p style={{ color: "var(--esb-muted)", fontSize: "13px" }}>per year</p>
              </div>
              <ul style={{ listStyle: "none", padding: 0, margin: "0 0 24px", flex: 1 }}>
                {[
                  "Access to practitioner portal",
                  "ESB referral eligibility",
                  "Practitioner network access",
                  "Curriculum and tools",
                  "12-month tail on lapse",
                ].map((f) => (
                  <li key={f} style={{ display: "flex", alignItems: "flex-start", gap: "8px", marginBottom: "8px", fontSize: "14px" }}>
                    <span style={{ color: "var(--esb-primary)", fontSize: "16px", lineHeight: "1.4" }}>✓</span>
                    {f}
                  </li>
                ))}
              </ul>
              {status?.has_membership ? (
                <div>
                  <div style={{ display: "inline-block", background: "#e8f5e9", color: "#2e7d32", fontSize: "13px", fontWeight: 700, padding: "6px 14px", borderRadius: "4px", marginBottom: "8px" }}>
                    {status.membership_status === "active" ? "Active" : status.membership_status}
                  </div>
                  {status.membership_until && (
                    <p style={{ fontSize: "12px", color: "var(--esb-muted)", margin: 0 }}>
                      Renews {new Date(status.membership_until).toLocaleDateString()}
                    </p>
                  )}
                </div>
              ) : (
                <button
                  className="btn-primary"
                  onClick={() => startCheckout("membership")}
                  disabled={actionLoading === "membership"}
                  style={{ opacity: actionLoading === "membership" ? 0.7 : 1 }}
                >
                  {actionLoading === "membership" ? "Redirecting…" : "Join — $2,500/yr"}
                </button>
              )}
            </div>

            {/* Certification */}
            <div className="esb-card" style={{ display: "flex", flexDirection: "column", border: "2px solid var(--esb-primary)" }}>
              <div style={{ marginBottom: "16px" }}>
                <span style={{ background: "var(--esb-primary)", color: "#fff", fontSize: "11px", fontWeight: 700, padding: "3px 8px", borderRadius: "3px", textTransform: "uppercase" }}>
                  Recommended
                </span>
                <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "36px", fontWeight: 700, margin: "8px 0 4px" }}>$5,000</h2>
                <p style={{ color: "var(--esb-muted)", fontSize: "13px" }}>3-year certification</p>
              </div>
              <p style={{ fontSize: "13px", color: "var(--esb-text)", marginBottom: "12px", fontWeight: 600 }}>
                Certified Great on Their Behalf Practitioner
              </p>
              <ul style={{ listStyle: "none", padding: 0, margin: "0 0 24px", flex: 1 }}>
                {[
                  "Everything in membership",
                  "Administer Certified Assessments",
                  "Validated results for districts",
                  "Priority referral routing",
                  "3-year credential term",
                  "Signed practitioner agreement",
                ].map((f) => (
                  <li key={f} style={{ display: "flex", alignItems: "flex-start", gap: "8px", marginBottom: "8px", fontSize: "14px" }}>
                    <span style={{ color: "var(--esb-primary)", fontSize: "16px", lineHeight: "1.4" }}>✓</span>
                    {f}
                  </li>
                ))}
              </ul>
              {status?.has_certification ? (
                <div>
                  <div style={{ display: "inline-block", background: "#e8f5e9", color: "#2e7d32", fontSize: "13px", fontWeight: 700, padding: "6px 14px", borderRadius: "4px", marginBottom: "8px" }}>
                    Certified
                  </div>
                  {status.certification_expires && (
                    <p style={{ fontSize: "12px", color: "var(--esb-muted)", margin: 0 }}>
                      Expires {new Date(status.certification_expires).toLocaleDateString()}
                    </p>
                  )}
                </div>
              ) : (
                <button
                  className="btn-primary"
                  onClick={() => startCheckout("certification")}
                  disabled={actionLoading === "certification" || !status?.has_membership}
                  title={!status?.has_membership ? "Active membership required" : undefined}
                  style={{ opacity: (actionLoading === "certification" || !status?.has_membership) ? 0.6 : 1 }}
                >
                  {actionLoading === "certification" ? "Redirecting…" : "Get Certified — $5,000"}
                </button>
              )}
              {!status?.has_membership && (
                <p style={{ fontSize: "12px", color: "var(--esb-muted)", marginTop: "8px" }}>Requires active membership</p>
              )}
            </div>

            {/* Stripe Connect */}
            <div className="esb-card" style={{ display: "flex", flexDirection: "column" }}>
              <div style={{ marginBottom: "16px" }}>
                <span style={{ fontFamily: "var(--font-heading)", fontSize: "12px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "1px", color: "var(--esb-muted)" }}>Disbursements</span>
                <h2 style={{ fontFamily: "var(--font-heading)", fontSize: "36px", fontWeight: 700, margin: "8px 0 4px" }}>85%</h2>
                <p style={{ color: "var(--esb-muted)", fontSize: "13px" }}>of referral revenue to you</p>
              </div>
              <p style={{ fontSize: "14px", color: "var(--esb-text)", marginBottom: "24px", flex: 1, lineHeight: "1.6" }}>
                Connect your bank account via Stripe to receive automatic disbursements when ESB-referred clients pay. ESB retains 15%; 85% transfers directly to you.
              </p>
              <button
                className="btn-outline"
                onClick={startConnect}
                disabled={actionLoading === "connect"}
                style={{ opacity: actionLoading === "connect" ? 0.7 : 1 }}
              >
                {actionLoading === "connect" ? "Redirecting…" : "Connect Bank Account"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
