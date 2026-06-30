"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { auth } from "@/lib/api";

const ADMIN_ROLES = ["superuser", "lead_senior_practitioner"];

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    auth
      .me()
      .then((me) => {
        const ok = me.roles.some((r) => ADMIN_ROLES.includes(r));
        if (!ok) router.push("/portal/dashboard");
        else setAuthorized(true);
      })
      .catch(() => router.push("/sign-in"));
  }, [router]);

  if (!authorized) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-esb-blue border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-gray-200 bg-esb-blue-dark text-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <span className="font-semibold tracking-tight">
            ESB Admin
          </span>
          <a href="/portal/dashboard" className="text-sm hover:text-esb-gold">
            Back to Portal
          </a>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-8">{children}</main>
    </div>
  );
}
