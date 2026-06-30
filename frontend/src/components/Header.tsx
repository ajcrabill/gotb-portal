"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import { auth, clearToken, type MeResponse } from "@/lib/api";

const ESB_SITE = "https://effectiveschoolboards.com";

type NavItem = {
  label: string;
  href: string;
  external?: boolean;
  dropdown?: { label: string; href: string; external?: boolean }[];
  portalOnly?: boolean;
};

const NAV_ITEMS: NavItem[] = [
  {
    label: "Framework",
    href: "#",
    external: true,
    dropdown: [
      { label: "The ESB Framework", href: `${ESB_SITE}/framework/`, external: true },
      { label: "Great on Their Behalf Index", href: "/portal/assessment" },
      { label: "State ESB Toolkit", href: `${ESB_SITE}/state-toolkit/`, external: true },
      { label: "ESB Newsletter", href: `${ESB_SITE}/newsletter/`, external: true },
    ],
  },
  {
    label: "Practitioners",
    href: "#",
    dropdown: [
      { label: "Find a Practitioner", href: `${ESB_SITE}/coaches/find/`, external: true },
      { label: "Become a Practitioner", href: `${ESB_SITE}/coaches/become/`, external: true },
      { label: "Become a Senior Practitioner", href: `${ESB_SITE}/coaches/senior/`, external: true },
      { label: "IRR Simulator", href: "/portal/irr-simulator", portalOnly: true },
      { label: "My Clients", href: "/portal/clients", portalOnly: true },
    ],
  },
  {
    label: "Resources",
    href: "#",
    dropdown: [
      { label: "Time Use Evaluation", href: "/portal/assessment#time-use" },
      { label: "Board Self Evaluation", href: `${ESB_SITE}/resources/board-self-eval/`, external: true },
      { label: "Superintendent Evaluation", href: `${ESB_SITE}/resources/supt-eval/`, external: true },
      { label: "Goal & Guardrail Examples", href: `${ESB_SITE}/resources/goals/`, external: true },
      { label: "Implementation Plan", href: "/plan", external: true },
      { label: "Glossary", href: `${ESB_SITE}/resources/glossary/`, external: true },
      { label: "Community Discussion", href: `${ESB_SITE}/community/`, external: true },
    ],
  },
  {
    label: "Contact",
    href: `${ESB_SITE}/contact/`,
    external: true,
  },
];

const PORTAL_NAV: NavItem[] = [
  { label: "Dashboard", href: "/portal/dashboard" },
  { label: "Assessment", href: "/portal/assessment" },
  { label: "IRR Simulator", href: "/portal/irr-simulator" },
];

export default function Header() {
  const pathname = usePathname();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [me, setMe] = useState<MeResponse | null>(null);
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    auth.me().then(setMe).catch(() => {});
  }, []);

  const isPortal = pathname?.startsWith("/portal") || pathname?.startsWith("/admin");
  const isAdmin = me?.roles.some((r) => ["superuser", "lead_senior_practitioner"].includes(r));

  async function handleLogout() {
    await auth.logout();
    clearToken();
    window.location.href = "/sign-in";
  }

  return (
    <header
      id="header"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 997,
        background: "#fff",
        transition: "all 0.5s",
        padding: scrolled ? "12px 0" : "20px 0",
        boxShadow: scrolled ? "0px 2px 15px rgba(0,0,0,0.1)" : "none",
      }}
    >
      <div className="container mx-auto px-4 flex items-center justify-between">
        {/* Logo */}
        <a
          href={isPortal ? "/portal/dashboard" : ESB_SITE}
          style={{ fontFamily: "var(--font-logo)", fontSize: "22px", fontWeight: 600, color: "#111111", textDecoration: "none" }}
        >
          Effective{" "}
          <span style={{ color: "var(--esb-primary)" }}>School Boards</span>
        </a>

        {/* Desktop nav */}
        <nav className="hidden lg:flex items-center gap-0">
          {NAV_ITEMS.map((item) => (
            <div
              key={item.label}
              className="relative group"
              onMouseEnter={() => setOpenDropdown(item.label)}
              onMouseLeave={() => setOpenDropdown(null)}
            >
              <a
                href={item.href}
                target={item.external ? "_blank" : undefined}
                rel={item.external ? "noopener noreferrer" : undefined}
                style={{
                  fontFamily: "var(--font-heading)",
                  fontSize: "15px",
                  fontWeight: 600,
                  color: "#111111",
                  textDecoration: "none",
                  padding: "10px 0 10px 30px",
                  display: "block",
                  transition: "color 0.3s",
                }}
                className="hover:text-[color:var(--esb-primary)]"
              >
                {item.label}
                {item.dropdown && (
                  <i style={{ marginLeft: "4px", fontSize: "11px" }}>▾</i>
                )}
              </a>

              {/* Dropdown */}
              {item.dropdown && (
                <div
                  style={{
                    position: "absolute",
                    top: "100%",
                    left: "30px",
                    background: "#fff",
                    boxShadow: "0px 0px 30px rgba(127,137,161,0.25)",
                    padding: "10px 0",
                    minWidth: "220px",
                    zIndex: 999,
                    opacity: openDropdown === item.label ? 1 : 0,
                    visibility: openDropdown === item.label ? "visible" : "hidden",
                    transition: "opacity 0.3s",
                  }}
                >
                  {item.dropdown.map((sub) => (
                    <a
                      key={sub.label}
                      href={sub.href}
                      target={sub.external ? "_blank" : undefined}
                      rel={sub.external ? "noopener noreferrer" : undefined}
                      style={{
                        display: "block",
                        padding: "10px 25px",
                        fontFamily: "var(--font-sans)",
                        fontSize: "14px",
                        color: "#444444",
                        textDecoration: "none",
                        transition: "color 0.3s, background 0.3s",
                        whiteSpace: "nowrap",
                      }}
                      className="hover:text-[color:var(--esb-primary)] hover:bg-gray-50"
                    >
                      {sub.label}
                      {sub.portalOnly && (
                        <span
                          style={{
                            marginLeft: "8px",
                            fontSize: "10px",
                            background: "var(--esb-primary)",
                            color: "#fff",
                            padding: "1px 5px",
                            borderRadius: "10px",
                          }}
                        >
                          Portal
                        </span>
                      )}
                    </a>
                  ))}
                </div>
              )}
            </div>
          ))}

          {/* Portal-specific right side */}
          {isPortal && me ? (
            <div className="flex items-center gap-2 ml-8">
              {isAdmin && (
                <a
                  href="/admin/dashboard"
                  style={{
                    fontFamily: "var(--font-heading)",
                    fontSize: "13px",
                    fontWeight: 600,
                    color: "#444",
                    textDecoration: "none",
                    padding: "6px 16px",
                    border: "1px solid var(--esb-border)",
                    borderRadius: "4px",
                  }}
                >
                  Admin
                </a>
              )}
              <button
                onClick={handleLogout}
                className="btn-primary"
                style={{ padding: "8px 20px", fontSize: "14px" }}
              >
                Sign Out
              </button>
            </div>
          ) : (
            <a
              href="/sign-in"
              className="btn-primary ml-8"
              style={{ padding: "8px 20px", fontSize: "14px" }}
            >
              Sign In
            </a>
          )}
        </nav>

        {/* Mobile toggle */}
        <button
          className="lg:hidden"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle navigation"
          style={{ border: "none", background: "none", cursor: "pointer" }}
        >
          <div style={{ width: "24px", height: "2px", background: "#111", margin: "5px 0", transition: "0.3s" }} />
          <div style={{ width: "24px", height: "2px", background: "#111", margin: "5px 0" }} />
          <div style={{ width: "24px", height: "2px", background: "#111", margin: "5px 0" }} />
        </button>
      </div>

      {/* Mobile nav */}
      {mobileOpen && (
        <div
          style={{
            background: "#fff",
            borderTop: "1px solid var(--esb-border)",
            padding: "20px",
          }}
        >
          {NAV_ITEMS.map((item) => (
            <div key={item.label} style={{ marginBottom: "12px" }}>
              <a
                href={item.dropdown ? "#" : item.href}
                style={{
                  fontFamily: "var(--font-heading)",
                  fontSize: "15px",
                  fontWeight: 600,
                  color: "#111111",
                  textDecoration: "none",
                }}
              >
                {item.label}
              </a>
              {item.dropdown && (
                <div style={{ paddingLeft: "16px", marginTop: "8px" }}>
                  {item.dropdown.map((sub) => (
                    <a
                      key={sub.label}
                      href={sub.href}
                      style={{
                        display: "block",
                        padding: "6px 0",
                        fontSize: "14px",
                        color: "#444",
                        textDecoration: "none",
                      }}
                    >
                      {sub.label}
                    </a>
                  ))}
                </div>
              )}
            </div>
          ))}
          <div style={{ marginTop: "16px", borderTop: "1px solid var(--esb-border)", paddingTop: "16px" }}>
            {me ? (
              <button onClick={handleLogout} className="btn-primary w-full">
                Sign Out
              </button>
            ) : (
              <a href="/sign-in" className="btn-primary block text-center">
                Sign In
              </a>
            )}
          </div>
        </div>
      )}
    </header>
  );
}
