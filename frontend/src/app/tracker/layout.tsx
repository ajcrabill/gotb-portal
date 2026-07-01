"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { auth } from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";

const TRACKER_ROLES = ["superuser", "lead_senior_practitioner", "facilitation_manager"];

export default function TrackerLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    auth
      .me()
      .then((me) => {
        if (me.roles.some((r) => TRACKER_ROLES.includes(r))) setAuthorized(true);
        else router.push("/portal/dashboard");
      })
      .catch(() => router.push("/sign-in"));
  }, [router]);

  if (!authorized) {
    return (
      <div style={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center" }}>
        <div
          style={{
            width: "40px",
            height: "40px",
            border: "4px solid var(--esb-primary)",
            borderTopColor: "transparent",
            borderRadius: "50%",
            animation: "spin 0.8s linear infinite",
          }}
        />
        <style>{`@keyframes spin { to { transform: rotate(360deg); }}`}</style>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <Header />
      <main style={{ flex: 1, paddingTop: "82px" }}>
        <div
          className="esb-breadcrumb"
          style={{ background: "var(--esb-section-dark)", marginTop: "82px", padding: "20px 0" }}
        >
          <div className="container mx-auto px-4">
            <h2 style={{ color: "#fff", fontSize: "22px", fontWeight: 500, margin: 0 }}>
              Coach Progress Tracker
            </h2>
          </div>
        </div>
        <div className="container mx-auto px-4 py-8">{children}</div>
      </main>
      <Footer />
    </div>
  );
}
