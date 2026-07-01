"""The dossier pipeline: deterministic orchestration with three LLM seams.

Ported from coach-devon's dossier/pipeline.py. Stages: PLAN -> GATHER ->
EXTRACT* -> VERIFY* -> SUMMARIZE* -> PERSIST (* = skipped if no LLM key,
leaving a valid gather-only dossier with a full search log and zero
fabricated claims). Uses sync SQLAlchemy (see esb/crm/sync_db.py) — same
reasoning as the verifier port.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from esb.crm import connectors as C
from esb.crm import llm
from esb.models.crm import CrmClaim, CrmDistrict, CrmDossier, CrmEmail, CrmPerson, CrmSearch, CrmSubscriber

EXTRACT_SYS = (
    "You extract verifiable biographical/professional facts about a US school "
    "district superintendent or board member from a single source document. "
    "Return JSON: {\"claims\":[{\"field\":\"...\",\"value\":\"...\","
    "\"source_url\":\"<MUST equal the provided url>\",\"stated_confidence\":0-1}]}. "
    "Only facts present in the text. If none, return {\"claims\":[]}."
)
VERIFY_SYS = (
    "You are an adversarial fact-checker. Given a claim and the source text it "
    "supposedly comes from, decide if the text supports it. Return JSON: "
    "{\"verdict\":\"confirmed|partial|false|insufficient\",\"evidence_quote\":\"...\"}. "
    "You do NOT see how the claim was produced — judge only against the text."
)
SUMMARIZE_SYS = (
    "You write a tight 2-4 sentence intelligence summary of a school district "
    "leader for outreach personalization, using only the supplied confirmed facts. "
    "Return JSON: {\"summary\":\"...\"}."
)


def _subscriber_fact(session: Session, dossier: CrmDossier, person: CrmPerson | None) -> None:
    """Newsletter-subscription status is a first-class, first-hand fact."""
    if not person:
        return
    emails = [e.email for e in session.execute(select(CrmEmail).where(CrmEmail.person_id == person.id)).scalars().all()]
    if not emails:
        return
    sub = session.execute(select(CrmSubscriber).where(CrmSubscriber.email.in_(emails))).scalars().first()
    if sub:
        session.add(CrmClaim(
            dossier_id=dossier.id, field="newsletter_subscriber",
            value=f"Already subscribes to The Effective School Board Member ({sub.tier} tier, {sub.status})",
            confidence=1.0, source_url="beehiiv:subscription",
            source_tier="first_hand", verdict="confirmed"))


def plan(subject: str, district: CrmDistrict | None, role: str) -> list[tuple[str, str]]:
    dn = district.name if district else ""
    st = district.state if district else ""
    queries = [
        ("wikipedia", subject),
        ("web", f"{subject} {dn} {st} {role}".strip()),
        ("news", f'"{subject}" {dn}'.strip()),
    ]
    if dn:
        queries.append(("news", f"{dn} school board"))
    return queries


def gather(session: Session, dossier: CrmDossier, subject: str, district: CrmDistrict | None, role: str) -> list[C.Doc]:
    docs: list[C.Doc] = []
    for kind, query in plan(subject, district, role):
        if kind == "wikipedia":
            results = C.wikipedia(query)
        elif kind == "web":
            results = C.web_search(query)
        else:
            results = C.news(query)
        for d in results:
            session.add(CrmSearch(dossier_id=dossier.id, method=d.method, source=d.source,
                                   query=query, url=d.url, found=d.found, notes=d.title[:200]))
            if d.found and d.url:
                docs.append(d)
    session.commit()

    for d in docs:
        if not d.text and d.source in ("web", "news"):
            d.text = C.fetch_text(d.url)
    return [d for d in docs if d.text]


def extract_claims(session: Session, dossier: CrmDossier, docs: list[C.Doc]) -> int:
    n = 0
    for d in docs:
        try:
            out = llm.complete_json_sync(EXTRACT_SYS, f"url: {d.url}\nsource: {d.source}\ntext:\n{d.text[:6000]}")
        except Exception:
            continue
        for c in out.get("claims", []):
            if c.get("source_url") != d.url:
                continue
            session.add(CrmClaim(
                dossier_id=dossier.id, field=str(c.get("field", ""))[:120],
                value=str(c.get("value", ""))[:2000], source_url=d.url,
                source_tier="professional" if d.source != "social" else "social",
                confidence=float(c.get("stated_confidence", 0.0) or 0.0),
            ))
            n += 1
    session.commit()
    return n


def verify_claims(session: Session, dossier: CrmDossier, docs_by_url: dict[str, str]) -> None:
    claims = session.execute(select(CrmClaim).where(CrmClaim.dossier_id == dossier.id)).scalars().all()
    for claim in claims:
        text = docs_by_url.get(claim.source_url, "")
        if not text:
            claim.verdict = "insufficient"
            continue
        try:
            out = llm.complete_json_sync(VERIFY_SYS, f"claim: {claim.field} = {claim.value}\nsource text:\n{text[:5000]}")
            claim.verdict = out.get("verdict", "insufficient")
            if claim.verdict == "confirmed":
                claim.confidence = max(claim.confidence, 0.9)
            elif claim.verdict == "false":
                claim.confidence = 0.0
        except Exception:
            claim.verdict = "insufficient"
    session.commit()


def summarize(session: Session, dossier: CrmDossier) -> None:
    claims = session.execute(select(CrmClaim).where(CrmClaim.dossier_id == dossier.id)).scalars().all()
    good = [c for c in claims if c.verdict in ("confirmed", "partial")]
    if not good:
        return
    facts = "\n".join(f"- {c.field}: {c.value}" for c in good[:30])
    try:
        out = llm.complete_json_sync(SUMMARIZE_SYS, f"subject: {dossier.subject_name}\nconfirmed facts:\n{facts}")
        dossier.summary = out.get("summary", "")[:4000]
    except Exception:
        pass
    session.commit()


def create_dossier(
    session: Session, subject: str, person: CrmPerson | None, district: CrmDistrict | None,
) -> CrmDossier:
    """Fast, synchronous — just the initial row so callers get a pollable id back immediately."""
    dossier = CrmDossier(
        subject_name=subject,
        person_id=person.id if person else None,
        district_id=district.id if district else None,
        status="gathering",
    )
    session.add(dossier)
    session.commit()
    return dossier


def run_pipeline(
    session: Session, dossier: CrmDossier, subject: str, person: CrmPerson | None,
    district: CrmDistrict | None, role: str = "",
) -> CrmDossier:
    """The actual research pass — can take well over a minute. Call this from
    a background task against an already-created dossier row (see create_dossier)."""
    docs = gather(session, dossier, subject, district, role)

    if not llm.configured():
        dossier.status = "needs_llm"
        session.commit()
        return dossier

    extract_claims(session, dossier, docs)
    verify_claims(session, dossier, {d.url: d.text for d in docs})
    _subscriber_fact(session, dossier, person)
    summarize(session, dossier)
    dossier.status = "complete"
    session.commit()
    return dossier


def build(session: Session, subject: str, person: CrmPerson | None, district: CrmDistrict | None, role: str = "") -> CrmDossier:
    """Synchronous end-to-end build — kept for direct/scripted use. Routers
    should use create_dossier + run_pipeline separately so they can return
    a pollable id before the (potentially minutes-long) research pass runs."""
    dossier = create_dossier(session, subject, person, district)
    return run_pipeline(session, dossier, subject, person, district, role)
