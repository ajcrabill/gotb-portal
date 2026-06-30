"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { auth } from "@/lib/api";
import Header from "@/components/Header";
import Footer from "@/components/Footer";

export default function PortalLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    auth
      .me()
      .then(() => setReady(true))
      .catch(() => router.push("/sign-in"));
  }, [router]);

  if (!ready) {
    return (
      <div
        style={{
          display: "flex",
          minHeight: "100vh",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
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
        {children}
      </main>
      <Footer />
    </div>
  );
}
