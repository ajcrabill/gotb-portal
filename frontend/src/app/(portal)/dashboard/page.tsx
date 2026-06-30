"use client";

import { useEffect, useState } from "react";
import { auth, type MeResponse } from "@/lib/api";

export default function DashboardPage() {
  const [me, setMe] = useState<MeResponse | null>(null);

  useEffect(() => {
    auth.me().then(setMe).catch(() => {});
  }, []);

  const isFacilitator =
    me?.roles.some((r) =>
      ["certified_facilitator", "senior_facilitator", "coaching_manager",
       "lead_senior_practitioner", "superuser"].includes(r)
    ) ?? false;

  const isClient = me?.roles.includes("client") ?? false;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-esb-blue-dark">Dashboard</h1>

      {isFacilitator && (
        <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">Practitioner Tools</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <DashCard
              title="IRR Simulator"
              description="Practice inter-rater reliability with dynamically generated scenarios."
              href="/portal/irr-simulator"
            />
            <DashCard
              title="My Clients"
              description="View and manage your active client relationships."
              href="/portal/clients"
            />
            <DashCard
              title="Assessments"
              description="Schedule and conduct certified assessments."
              href="/portal/assessments"
            />
          </div>
        </section>
      )}

      {isClient && (
        <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold">Your Board</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <DashCard
              title="Great on Their Behalf Index"
              description="View your board's indicative self-assessment results."
              href="/portal/assessment"
            />
            <DashCard
              title="Implementation Plan"
              description="Track your board's development roadmap."
              href="/plan"
            />
          </div>
        </section>
      )}
    </div>
  );
}

function DashCard({
  title,
  description,
  href,
}: {
  title: string;
  description: string;
  href: string;
}) {
  return (
    <a
      href={href}
      className="block rounded-lg border border-gray-200 p-4 transition hover:border-esb-blue hover:shadow-md"
    >
      <h3 className="font-semibold text-esb-blue-dark">{title}</h3>
      <p className="mt-1 text-sm text-esb-slate">{description}</p>
    </a>
  );
}
