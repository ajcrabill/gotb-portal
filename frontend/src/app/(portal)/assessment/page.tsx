"use client";

/**
 * Self-assessment entry point — the indicative Great on Their Behalf Index.
 *
 * CRITICAL: This is indicative / self-scored / unvalidated.
 * The disclaimer must appear prominently and cannot be removed.
 * Certified Assessment (validated tier) is a separate flow, accessible
 * only to practitioners with the credential.
 */
import { useTranslations } from "next-intl";

export default function AssessmentPage() {
  const t = useTranslations("assessment");

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
        <p className="text-sm text-amber-800">
          <strong>{t("indicativeLabel")}: </strong>
          {t("indicativeDisclaimer")}
        </p>
      </div>

      <h1 className="text-2xl font-bold text-esb-blue-dark">
        {t("selfAssessmentTitle")}
      </h1>
      <p className="text-esb-slate">{t("selfAssessmentDescription")}</p>

      {/* Practice scoring panels — Phase 1 */}
      <div className="rounded-lg border border-gray-200 bg-white p-8 text-center text-esb-slate">
        Assessment instrument — Phase 1
      </div>
    </div>
  );
}
