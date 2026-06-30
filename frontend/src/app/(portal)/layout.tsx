"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { auth, clearToken, type MeResponse } from "@/lib/api";

export default function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const t = useTranslations("nav");
  const [me, setMe] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    auth
      .me()
      .then(setMe)
      .catch(() => router.push("/sign-in"))
      .finally(() => setLoading(false));
  }, [router]);

  async function handleLogout() {
    await auth.logout();
    clearToken();
    router.push("/sign-in");
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-esb-blue border-t-transparent" />
      </div>
    );
  }

  const isAdmin =
    me?.roles.includes("superuser") ||
    me?.roles.includes("lead_senior_practitioner");

  return (
    <div className="min-h-screen">
      <header className="border-b border-gray-200 bg-esb-blue-dark text-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <span className="font-semibold tracking-tight">
            Effective School Boards
          </span>
          <nav className="flex items-center gap-4 text-sm">
            <a href="/portal/dashboard" className="hover:text-esb-gold">
              {t("dashboard")}
            </a>
            {isAdmin && (
              <a href="/admin/dashboard" className="hover:text-esb-gold">
                {t("admin")}
              </a>
            )}
            <button
              onClick={handleLogout}
              className="hover:text-esb-gold"
            >
              {t("signOut")}
            </button>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-8">{children}</main>
    </div>
  );
}
