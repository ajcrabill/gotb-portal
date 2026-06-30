"use client";

export default function AdminDashboardPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-esb-blue-dark">Admin</h1>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <AdminCard
          title="People"
          description="Manage persons, roles, and certifications."
          href="/admin/people"
        />
        <AdminCard
          title="Districts"
          description="View districts and CGCS flags."
          href="/admin/districts"
        />
        <AdminCard
          title="Scoring Config"
          description="View active scoring configuration version."
          href="/admin/scoring"
        />
        <AdminCard
          title="Audit Log"
          description="WORM audit trail — read-only."
          href="/admin/audit"
        />
        <AdminCard
          title="Pipeline Queue"
          description="Review held content awaiting CM approval."
          href="/admin/pipeline-queue"
        />
        <AdminCard
          title="IRR Scenarios"
          description="Manage IRR simulator scenario templates."
          href="/admin/irr-scenarios"
        />
      </div>
    </div>
  );
}

function AdminCard({
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
      className="block rounded-lg border border-gray-200 bg-white p-4 transition hover:border-esb-blue hover:shadow-md"
    >
      <h3 className="font-semibold text-esb-blue-dark">{title}</h3>
      <p className="mt-1 text-sm text-esb-slate">{description}</p>
    </a>
  );
}
