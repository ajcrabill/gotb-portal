"use client";

import { useEffect, useState } from "react";
import { auth, type MeResponse } from "@/lib/api";

type DashCard = { title: string; description: string; href: string; tag?: string };

const PRACTITIONER_CARDS: DashCard[] = [
  {
    title: "Time Use Evaluation IRR Simulator",
    description: "Practice inter-rater reliability with dynamically generated board meeting scenarios. Reach κ ≥ 0.70 to certify.",
    href: "/portal/irr-simulator",
    tag: "Practice",
  },
  {
    title: "My Clients",
    description: "View and manage your active client districts, scheduled assessments, and implementation timelines.",
    href: "/portal/clients",
    tag: "Clients",
  },
  {
    title: "Certified Assessments",
    description: "Schedule and administer validated Great on Their Behalf assessments for client districts.",
    href: "/portal/assessments",
    tag: "Assessments",
  },
  {
    title: "Referrals",
    description: "Review district referrals routed to you by Effective School Boards.",
    href: "/portal/referrals",
    tag: "Referrals",
  },
  {
    title: "Time Use Evaluation",
    description: "Submit a board meeting video for automated time-use classification and a coaching report.",
    href: "/portal/time-use-eval",
    tag: "Evaluation",
  },
];

const CLIENT_CARDS: DashCard[] = [
  {
    title: "Great on Their Behalf Index",
    description: "Take your board's indicative self-assessment and see where you stand across the five practices.",
    href: "/portal/assessment",
    tag: "Indicative",
  },
  {
    title: "Implementation Plan",
    description: "Track your board's development roadmap and see recommended next steps.",
    href: "/plan",
    tag: "Planning",
  },
  {
    title: "Your Practitioner",
    description: "Connect with your Effective School Boards practitioner and review session history.",
    href: "/portal/my-practitioner",
    tag: "Support",
  },
];

export default function DashboardPage() {
  const [me, setMe] = useState<MeResponse | null>(null);

  useEffect(() => {
    auth.me().then(setMe).catch(() => {});
  }, []);

  const isPractitioner = me?.roles.some((r) =>
    ["certified_practitioner", "senior_practitioner", "practitioner_manager",
     "lead_senior_practitioner", "superuser"].includes(r)
  );
  const isClient = me?.roles.includes("client");

  return (
    <div>
      {/* Page header strip */}
      <div
        style={{
          background: "var(--esb-section-dark)",
          padding: "40px 0 30px",
          color: "#fff",
        }}
      >
        <div className="container mx-auto px-4">
          <h1
            style={{
              fontFamily: "var(--font-heading)",
              fontSize: "34px",
              fontWeight: 700,
              color: "#fff",
              margin: 0,
            }}
          >
            Dashboard
          </h1>
          <p style={{ color: "#aaaaaa", marginTop: "8px", marginBottom: 0 }}>
            Welcome to the Effective School Boards Portal
          </p>
        </div>
      </div>

      <div className="container mx-auto px-4 py-12">

        {isPractitioner && (
          <section style={{ marginBottom: "48px" }}>
            <div className="section-title" style={{ textAlign: "left", paddingBottom: "20px" }}>
              <h2
                style={{
                  fontFamily: "var(--font-heading)",
                  fontSize: "24px",
                  fontWeight: 700,
                  color: "var(--esb-dark)",
                  position: "relative",
                  paddingBottom: "12px",
                  marginBottom: "4px",
                }}
              >
                Practitioner Tools
                <span
                  style={{
                    position: "absolute",
                    bottom: 0,
                    left: 0,
                    width: "40px",
                    height: "3px",
                    background: "var(--esb-primary)",
                  }}
                />
              </h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
              {PRACTITIONER_CARDS.map((card) => (
                <DashboardCard key={card.title} {...card} />
              ))}
            </div>
          </section>
        )}

        {isClient && (
          <section>
            <div style={{ paddingBottom: "20px" }}>
              <h2
                style={{
                  fontFamily: "var(--font-heading)",
                  fontSize: "24px",
                  fontWeight: 700,
                  color: "var(--esb-dark)",
                  position: "relative",
                  paddingBottom: "12px",
                }}
              >
                Your Board
                <span
                  style={{
                    position: "absolute",
                    bottom: 0,
                    left: 0,
                    width: "40px",
                    height: "3px",
                    background: "var(--esb-primary)",
                  }}
                />
              </h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {CLIENT_CARDS.map((card) => (
                <DashboardCard key={card.title} {...card} />
              ))}
            </div>
          </section>
        )}

        {!isPractitioner && !isClient && (
          <div
            className="esb-card"
            style={{ textAlign: "center", padding: "60px 30px" }}
          >
            <h3
              style={{
                fontFamily: "var(--font-heading)",
                fontSize: "22px",
                color: "var(--esb-dark)",
                marginBottom: "12px",
              }}
            >
              Access Pending
            </h3>
            <p style={{ color: "var(--esb-muted)", maxWidth: "400px", margin: "0 auto" }}>
              Your account has been created. Contact your Effective School Boards coordinator to
              have your role assigned.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function DashboardCard({ title, description, href, tag }: DashCard) {
  return (
    <a
      href={href}
      className="esb-card"
      style={{
        display: "block",
        textDecoration: "none",
        position: "relative",
        overflow: "hidden",
        transition: "transform 0.2s, box-shadow 0.2s",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.transform = "translateY(-2px)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.transform = "translateY(0)";
      }}
    >
      {tag && (
        <span
          style={{
            position: "absolute",
            top: "16px",
            right: "16px",
            background: "var(--esb-primary)",
            color: "#fff",
            fontSize: "11px",
            fontWeight: 600,
            fontFamily: "var(--font-heading)",
            padding: "2px 10px",
            borderRadius: "50px",
            textTransform: "uppercase",
            letterSpacing: "0.5px",
          }}
        >
          {tag}
        </span>
      )}
      <h3
        style={{
          fontFamily: "var(--font-heading)",
          fontSize: "18px",
          fontWeight: 700,
          color: "var(--esb-dark)",
          marginBottom: "10px",
        }}
      >
        {title}
      </h3>
      <p style={{ color: "var(--esb-text)", fontSize: "14px", lineHeight: "1.6", marginBottom: 0 }}>
        {description}
      </p>
    </a>
  );
}
