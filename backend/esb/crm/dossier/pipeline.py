"""The dossier pipeline: deterministic orchestration with three LLM seams.

Ported from coach-devon's dossier/pipeline.py, then substantially expanded
per AJ's 2026-07-01/07-02 requests: an exhaustive, markdown-deliverable
research tool with an adaptive matrix-search loop and per-technique
effectiveness tracking (dossier/stats.py). Stages: PLAN -> GATHER ->
EXTRACT* -> VERIFY* -> PIVOT (matrix search on discovered characteristics,
repeat) -> SCORE -> SUMMARIZE* -> RENDER -> PERSIST (* = skipped if no LLM
key, leaving a valid gather-only dossier with a full search log and zero
fabricated claims). Uses sync SQLAlchemy (see esb/crm/sync_db.py) — same
reasoning as the verifier port.

See RESEARCH_PLAN.md for the source strategy and confidence rubric this
implements.
"""
from __future__ import annotations

import urllib.parse

from sqlalchemy import select
from sqlalchemy.orm import Session

from esb.crm import connectors as C
from esb.crm import llm
from esb.crm.dossier import nces, wayback
from esb.crm.dossier.render import render_markdown
from esb.crm.dossier.scoring import classify_source_tier, score_claims
from esb.crm.newsworthy import HIGH as SCRUTINY_TERMS
from esb.models.crm import CrmClaim, CrmDistrict, CrmDossier, CrmEmail, CrmPerson, CrmSearch, CrmSubscriber

EXTRACT_SYS = (
    "You extract verifiable biographical/professional facts about a US school "
    "district superintendent, board member, or the district itself from a "
    "single source document. Return JSON: {\"claims\":[{\"field\":\"...\","
    "\"value\":\"...\",\"source_url\":\"<MUST equal the provided url>\","
    "\"stated_confidence\":0-1}]}. Use a short snake_case field name that "
    "reflects the CATEGORY of fact (e.g. title, career_prior_role, "
    "career_employer, education_degree, education_institution, lawsuit, "
    "board_vote, campaign_donor, affiliation, enrollment, budget, "
    "test_score) so it can be filed under the right dossier section and, "
    "for career/education/affiliation facts, used as a pivot for further "
    "search. Only facts present in the text. Never infer or guess. If none, "
    "return {\"claims\":[]}."
)
VERIFY_SYS = (
    "You are an adversarial fact-checker. Given a claim and the source text it "
    "supposedly comes from, decide if the text supports it. Return JSON: "
    "{\"verdict\":\"confirmed|partial|false|insufficient\",\"evidence_quote\":\"...\"}. "
    "You do NOT see how the claim was produced — judge only against the text."
)
SUMMARIZE_SYS = (
    "You write a tight 2-4 sentence intelligence summary for a practitioner "
    "about to meet this person or district for the first time, using only "
    "the supplied confirmed facts. Return JSON: {\"summary\":\"...\"}."
)

# Matrix-search pivot config. Field-name substrings worth spinning into a
# "<subject>" "<discovered characteristic>" follow-up query — e.g. a
# confirmed education_institution of "Ohio State" becomes its own deep
# search. Each hint is tracked as its own technique label
# (matrix:education, matrix:career, ...) so effectiveness can be measured
# and weak ones dropped from this list later — see dossier/stats.py.
_PIVOT_HINTS = ["education", "career", "employer", "prior_role", "former", "affiliation", "board_member_of", "network"]
_MAX_PIVOTS_PER_ROUND = 6
_MAX_PIVOT_ROUNDS = 2


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
            source_tier="primary", verdict="confirmed", technique="first_hand"))


def static_plan(subject: str, district: CrmDistrict | None, role: str, is_org: bool) -> list[tuple[str, str, bool, str]]:
    """The initial, fixed query batch. Returns (kind, query, deep, technique)
    tuples. deep=True queries go through the 5-engine/10-page-deep search;
    deep=False are single-shot (wikipedia/news RSS, which aren't paginated
    the same way)."""
    dn = district.name if district else ""
    st = district.state if district else ""
    queries: list[tuple[str, str, bool, str]] = []

    if is_org:
        queries += [
            ("web", f"{dn} {st} school district superintendent board", True, "static_broad"),
            ("news", f'"{dn}" school board', False, "news_district_board"),
            ("news", f'"{dn}" {st} superintendent', False, "news_district_supt"),
        ]
        for term in SCRUTINY_TERMS[:6]:
            queries.append(("web", f'"{dn}" {st} {term}', True, f"scrutiny:{term.replace(' ', '_')}"))
    else:
        queries += [
            ("wikipedia", subject, False, "wikipedia"),
            ("web", f"{subject} {dn} {st} {role}".strip(), True, "static_broad"),
            ("news", f'"{subject}" {dn}'.strip(), False, "news_subject_district"),
        ]
        if dn:
            queries.append(("news", f"{dn} school board", False, "news_district_board"))
        for term in SCRUTINY_TERMS[:6]:
            queries.append(("web", f'"{subject}" {term}', True, f"scrutiny:{term.replace(' ', '_')}"))

    return queries


def pivot_plan(subject: str, claims: list[CrmClaim], already_queried: set[str], max_pivots: int) -> list[tuple[str, str, bool, str]]:
    """Matrix search: for each confirmed/partial claim whose field matches a
    pivot-worthy category (education, career, affiliation, etc.), spin up a
    "<subject>" "<characteristic>" deep search. This is the literal
    <name> + <discovered characteristic> combination AJ asked for. Every
    pivot is tagged with its own technique label (matrix:<hint>) so
    effectiveness is trackable per-characteristic-type, not just "matrix"
    as one bucket."""
    items: list[tuple[str, str, bool, str]] = []
    seen_values: set[str] = set()
    for c in claims:
        if c.verdict not in ("confirmed", "partial"):
            continue
        field_l = c.field.lower()
        hint = next((h for h in _PIVOT_HINTS if h in field_l), None)
        if not hint:
            continue
        value = c.value.strip()
        if not value:
            continue
        value_key = value.lower()
        if value_key in seen_values:
            continue
        query = f'"{subject}" "{value}"'
        if query.lower() in already_queried:
            continue
        seen_values.add(value_key)
        items.append(("web", query, True, f"matrix:{hint}"))
        if len(items) >= max_pivots:
            break
    return items


def gather_batch(
    session: Session, dossier: CrmDossier, plan_items: list[tuple[str, str, bool, str]],
) -> list[tuple[C.Doc, str]]:
    """Run one batch of (kind, query, deep, technique) items. Logs a
    CrmSearch row per result, tagged with its technique. Returns
    (doc, technique) pairs for docs worth extracting from (found + text)."""
    pairs: list[tuple[C.Doc, str]] = []
    for kind, query, deep, technique in plan_items:
        if kind == "wikipedia":
            results = C.wikipedia(query)
        elif kind == "web":
            results = C.deep_web_search(query, pages=10) if deep else C.web_search(query)
        else:
            results = C.news(query)
        for d in results:
            session.add(CrmSearch(dossier_id=dossier.id, method=d.method, source=d.source,
                                   query=query, url=d.url, found=d.found, notes=d.title[:200],
                                   technique=technique))
            if d.found and d.url:
                pairs.append((d, technique))
    session.commit()

    for d, _t in pairs:
        if not d.text and d.source in ("web", "news"):
            d.text = C.fetch_text(d.url)

    return [(d, t) for d, t in pairs if d.text]


def gather(
    session: Session, dossier: CrmDossier, subject: str, district: CrmDistrict | None, role: str, is_org: bool,
) -> tuple[list[tuple[C.Doc, str]], str]:
    """The static (round 0) gather, plus the one-off NCES/Wayback lookups
    that aren't part of the query-matrix concept."""
    pairs = gather_batch(session, dossier, static_plan(subject, district, role, is_org))

    if is_org and district and district.nces_lea_id:
        nces_text = nces.fetch_district_detail_text(district.nces_lea_id)
        if nces_text:
            url = f"https://nces.ed.gov/ccd/districtsearch/district_detail.asp?ID2={district.nces_lea_id}"
            session.add(CrmSearch(dossier_id=dossier.id, method="nces_ccd", source="web",
                                   query="nces_lookup", url=url, found=True, notes="NCES CCD district detail",
                                   technique="nces_ccd"))
            pairs.append((C.Doc(source="web", method="nces_ccd", query="nces_lookup", url=url,
                                 title="NCES CCD District Detail", text=nces_text, found=True), "nces_ccd"))
    session.commit()

    wayback_note = ""
    if district and district.website:
        diff = wayback.earliest_and_latest_snapshot_text(district.website)
        if diff and diff["earliest_text"] and diff["earliest_text"] != diff["latest_text"]:
            wayback_note = (
                f"The district's official site has {diff['snapshot_count']} archived snapshots "
                f"({diff['earliest_date']} to {diff['latest_date']}). Content has changed since "
                f"the earliest capture — worth a manual look at "
                f"{wayback.snapshot_url(district.website, wayback.find_snapshots(district.website)[0]['timestamp'])} "
                f"if historical context matters here."
            )

    return pairs, wayback_note


def extract_claims(session: Session, dossier: CrmDossier, doc_pairs: list[tuple[C.Doc, str]], official_domain: str) -> int:
    n = 0
    for d, technique in doc_pairs:
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
                source_tier=classify_source_tier(d.url, official_domain),
                confidence=float(c.get("stated_confidence", 0.0) or 0.0),
                technique=technique,
            ))
            n += 1
    session.commit()
    return n


def verify_claims(session: Session, dossier: CrmDossier, docs_by_url: dict[str, str]) -> None:
    """Only verifies claims with no verdict yet — safe to call once per
    round without re-spending LLM calls on already-verified claims from
    earlier rounds."""
    claims = session.execute(
        select(CrmClaim).where(CrmClaim.dossier_id == dossier.id, CrmClaim.verdict == "")
    ).scalars().all()
    for claim in claims:
        text = docs_by_url.get(claim.source_url, "")
        if not text:
            claim.verdict = "insufficient"
            continue
        try:
            out = llm.complete_json_sync(VERIFY_SYS, f"claim: {claim.field} = {claim.value}\nsource text:\n{text[:5000]}")
            claim.verdict = out.get("verdict", "insufficient")
        except Exception:
            claim.verdict = "insufficient"
    session.commit()

    all_claims = session.execute(select(CrmClaim).where(CrmClaim.dossier_id == dossier.id)).scalars().all()
    score_claims(all_claims)
    session.commit()


def summarize(session: Session, dossier: CrmDossier) -> None:
    claims = session.execute(select(CrmClaim).where(CrmClaim.dossier_id == dossier.id)).scalars().all()
    good = [c for c in claims if c.verdict in ("confirmed", "partial") and c.confidence >= 0.9]
    if not good:
        return
    facts = "\n".join(f"- {c.field}: {c.value}" for c in good[:30])
    try:
        out = llm.complete_json_sync(SUMMARIZE_SYS, f"subject: {dossier.subject_name}\nconfirmed facts:\n{facts}")
        dossier.summary = out.get("summary", "")[:4000]
        from esb.crm.studio import voice_lint
        dossier.voice_flags = voice_lint(dossier.summary)
    except Exception:
        pass
    session.commit()


def create_dossier(
    session: Session, subject: str, person: CrmPerson | None, district: CrmDistrict | None,
    requested_by_id=None,
) -> CrmDossier:
    """Fast, synchronous — just the initial row so callers get a pollable id back immediately."""
    dossier = CrmDossier(
        subject_name=subject,
        person_id=person.id if person else None,
        district_id=district.id if district else None,
        requested_by_id=requested_by_id,
        status="gathering",
    )
    session.add(dossier)
    session.commit()
    return dossier


def run_pipeline(
    session: Session, dossier: CrmDossier, subject: str, person: CrmPerson | None,
    district: CrmDistrict | None, role: str = "",
) -> CrmDossier:
    """The actual research pass — an exhaustive build (5 engines, 10 pages
    deep, Wayback, NCES, plus up to 2 rounds of matrix-search pivots on
    discovered characteristics) can take well over ten minutes. Call this
    from a background task against an already-created dossier row (see
    create_dossier)."""
    is_org = person is None
    official_domain = ""
    if district and district.website:
        try:
            official_domain = urllib.parse.urlparse(district.website).netloc.lower().removeprefix("www.")
        except Exception:
            pass

    doc_pairs, wayback_note = gather(session, dossier, subject, district, role, is_org)

    if not llm.configured():
        dossier.status = "needs_llm"
        session.commit()
        return dossier

    queried = {q.lower() for _k, q, _d, _t in static_plan(subject, district, role, is_org)}

    extract_claims(session, dossier, doc_pairs, official_domain)
    verify_claims(session, dossier, {d.url: d.text for d, _t in doc_pairs})

    for _round in range(_MAX_PIVOT_ROUNDS):
        confirmed_so_far = session.execute(
            select(CrmClaim).where(CrmClaim.dossier_id == dossier.id)
        ).scalars().all()
        pivots = pivot_plan(subject, confirmed_so_far, queried, _MAX_PIVOTS_PER_ROUND)
        if not pivots:
            break
        queried.update(q.lower() for _k, q, _d, _t in pivots)

        pivot_docs = gather_batch(session, dossier, pivots)
        if not pivot_docs:
            continue
        extract_claims(session, dossier, pivot_docs, official_domain)
        verify_claims(session, dossier, {d.url: d.text for d, _t in pivot_docs})

    _subscriber_fact(session, dossier, person)
    session.commit()
    score_claims(session.execute(select(CrmClaim).where(CrmClaim.dossier_id == dossier.id)).scalars().all())
    session.commit()
    summarize(session, dossier)

    claims = session.execute(select(CrmClaim).where(CrmClaim.dossier_id == dossier.id)).scalars().all()
    searches = session.execute(select(CrmSearch).where(CrmSearch.dossier_id == dossier.id)).scalars().all()
    subject_label = f"{subject} ({district.name}, {district.state})" if is_org and district else subject
    dossier.markdown = render_markdown(dossier, claims, searches, is_org, subject_label, wayback_note)

    dossier.status = "complete"
    session.commit()
    return dossier


def build(session: Session, subject: str, person: CrmPerson | None, district: CrmDistrict | None, role: str = "") -> CrmDossier:
    """Synchronous end-to-end build — kept for direct/scripted use. Routers
    should use create_dossier + run_pipeline separately so they can return
    a pollable id before the (potentially many-minutes-long) research pass runs."""
    dossier = create_dossier(session, subject, person, district)
    return run_pipeline(session, dossier, subject, person, district, role)
