"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { auth, setToken } from "@/lib/api";

type Stage = "email" | "otp" | "done";

export default function SignInPage() {
  const t = useTranslations("auth");
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
      if (res.dev_otp) setDevOtp(res.dev_otp); // dev only
      setStage("otp");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("errorGeneric"));
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
      setStage("done");
      router.push("/portal/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("errorGeneric"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-esb-blue-dark">
            Effective School Boards Portal
          </h1>
          <p className="mt-2 text-sm text-esb-slate">
            {stage === "email" ? t("signInPrompt") : t("checkEmail")}
          </p>
        </div>

        {stage === "email" && (
          <form onSubmit={handleEmailSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-gray-700"
              >
                {t("emailLabel")}
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-esb-blue focus:outline-none"
                placeholder="you@district.org"
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-md bg-esb-blue px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 hover:bg-esb-blue-dark"
            >
              {loading ? t("sending") : t("sendCode")}
            </button>
          </form>
        )}

        {stage === "otp" && (
          <form onSubmit={handleOtpSubmit} className="space-y-4">
            <p className="text-sm text-gray-600">
              {t("codeSentTo", { email })}
            </p>
            {devOtp && (
              <div className="rounded bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800">
                Dev mode — OTP: <strong>{devOtp}</strong>
              </div>
            )}
            <div>
              <label
                htmlFor="code"
                className="block text-sm font-medium text-gray-700"
              >
                {t("codeLabel")}
              </label>
              <input
                id="code"
                type="text"
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                required
                autoComplete="one-time-code"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-center text-2xl font-mono tracking-widest shadow-sm focus:border-esb-blue focus:outline-none"
                placeholder="000000"
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-md bg-esb-blue px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 hover:bg-esb-blue-dark"
            >
              {loading ? t("verifying") : t("verify")}
            </button>
            <button
              type="button"
              onClick={() => { setStage("email"); setCode(""); setError(""); }}
              className="w-full text-sm text-esb-slate underline"
            >
              {t("changeEmail")}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
