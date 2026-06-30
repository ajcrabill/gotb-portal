"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { auth, setToken } from "@/lib/api";

type Stage = "email" | "otp";

export default function SignInPage() {
  const router = useRouter();
  const [stage, setStage] = useState<Stage>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [devOtp, setDevOtp] = useState<string | null>(null);

  async function handleEmailSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await auth.requestOtp(email.trim());
      if (res.dev_otp) setDevOtp(res.dev_otp);
      setStage("otp");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleOtpSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const session = await auth.verifyOtp(email.trim(), code.trim());
      setToken(session.token);
      router.push("/portal/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Invalid or expired code.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "var(--esb-light-bg)",
      }}
    >
      {/* Minimal header */}
      <header
        style={{
          background: "#fff",
          padding: "20px 0",
          boxShadow: "0px 2px 15px rgba(0,0,0,0.08)",
        }}
      >
        <div className="container mx-auto px-4">
          <a
            href="https://effectiveschoolboards.com"
            style={{
              fontFamily: "var(--font-logo)",
              fontSize: "22px",
              fontWeight: 600,
              color: "#111111",
              textDecoration: "none",
            }}
          >
            Effective{" "}
            <span style={{ color: "var(--esb-primary)" }}>School Boards</span>
          </a>
        </div>
      </header>

      {/* Page title strip */}
      <div
        style={{
          background: "var(--esb-section-dark)",
          padding: "30px 0",
          color: "#fff",
        }}
      >
        <div className="container mx-auto px-4">
          <h1
            style={{
              fontFamily: "var(--font-heading)",
              fontSize: "28px",
              fontWeight: 500,
              margin: 0,
              color: "#fff",
            }}
          >
            Portal Sign In
          </h1>
        </div>
      </div>

      {/* Form area */}
      <main
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "60px 20px",
        }}
      >
        <div
          className="esb-card"
          style={{ width: "100%", maxWidth: "440px" }}
        >
          {stage === "email" ? (
            <>
              <h2
                style={{
                  fontFamily: "var(--font-heading)",
                  fontSize: "22px",
                  fontWeight: 700,
                  marginBottom: "8px",
                  color: "var(--esb-dark)",
                }}
              >
                Welcome back
              </h2>
              <p style={{ color: "var(--esb-muted)", marginBottom: "28px", fontSize: "14px" }}>
                Enter your email address and we'll send you a sign-in code.
              </p>

              <form onSubmit={handleEmailSubmit}>
                <div style={{ marginBottom: "20px" }}>
                  <label
                    htmlFor="email"
                    style={{
                      display: "block",
                      fontFamily: "var(--font-heading)",
                      fontWeight: 600,
                      fontSize: "14px",
                      marginBottom: "6px",
                      color: "var(--esb-dark)",
                    }}
                  >
                    Email address
                  </label>
                  <input
                    id="email"
                    type="email"
                    required
                    autoComplete="email"
                    autoFocus
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="esb-input"
                    placeholder="you@district.org"
                  />
                </div>

                {error && (
                  <p
                    style={{
                      color: "#ed3c0d",
                      fontSize: "14px",
                      marginBottom: "16px",
                    }}
                  >
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="btn-primary"
                  style={{ width: "100%", textAlign: "center", opacity: loading ? 0.7 : 1 }}
                >
                  {loading ? "Sending…" : "Send sign-in code"}
                </button>
              </form>
            </>
          ) : (
            <>
              <h2
                style={{
                  fontFamily: "var(--font-heading)",
                  fontSize: "22px",
                  fontWeight: 700,
                  marginBottom: "8px",
                  color: "var(--esb-dark)",
                }}
              >
                Check your email
              </h2>
              <p style={{ color: "var(--esb-muted)", marginBottom: "8px", fontSize: "14px" }}>
                We sent a 6-digit code to <strong style={{ color: "var(--esb-dark)" }}>{email}</strong>.
              </p>

              {devOtp && (
                <div
                  style={{
                    background: "#fff3cd",
                    border: "1px solid #ffc107",
                    borderRadius: "4px",
                    padding: "10px 14px",
                    marginBottom: "20px",
                    fontSize: "13px",
                    color: "#856404",
                  }}
                >
                  <strong>Dev mode</strong> — your code is{" "}
                  <strong style={{ letterSpacing: "2px" }}>{devOtp}</strong>
                </div>
              )}

              <form onSubmit={handleOtpSubmit}>
                <div style={{ marginBottom: "20px" }}>
                  <label
                    htmlFor="code"
                    style={{
                      display: "block",
                      fontFamily: "var(--font-heading)",
                      fontWeight: 600,
                      fontSize: "14px",
                      marginBottom: "6px",
                      color: "var(--esb-dark)",
                    }}
                  >
                    6-digit code
                  </label>
                  <input
                    id="code"
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]{6}"
                    maxLength={6}
                    required
                    autoComplete="one-time-code"
                    autoFocus
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                    className="esb-input"
                    style={{
                      textAlign: "center",
                      fontSize: "28px",
                      fontWeight: 700,
                      letterSpacing: "8px",
                      fontFamily: "monospace",
                    }}
                    placeholder="000000"
                  />
                </div>

                {error && (
                  <p style={{ color: "#ed3c0d", fontSize: "14px", marginBottom: "16px" }}>
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="btn-primary"
                  style={{ width: "100%", textAlign: "center", opacity: loading ? 0.7 : 1 }}
                >
                  {loading ? "Verifying…" : "Verify code"}
                </button>

                <button
                  type="button"
                  onClick={() => { setStage("email"); setCode(""); setError(""); }}
                  style={{
                    marginTop: "12px",
                    width: "100%",
                    background: "none",
                    border: "none",
                    color: "var(--esb-muted)",
                    fontSize: "14px",
                    cursor: "pointer",
                    textDecoration: "underline",
                  }}
                >
                  Use a different email
                </button>
              </form>
            </>
          )}
        </div>
      </main>

      {/* Simple footer */}
      <footer
        style={{
          background: "var(--esb-footer-bg)",
          padding: "20px 0",
          color: "var(--esb-muted)",
          fontSize: "14px",
          textAlign: "center",
        }}
      >
        &copy; {new Date().getFullYear()} Effective School Boards
      </footer>
    </div>
  );
}
