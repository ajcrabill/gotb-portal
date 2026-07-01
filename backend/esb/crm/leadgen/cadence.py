"""The 10-touch cadence engine.

Ported from coach-devon's leadgen/cadence.py. Personalization variables are
extracted ONCE (one LLM call over the dossier + signal) and reused across
all touches; each touch is rendered DETERMINISTICALLY from the fixed
template — the model never writes the email, only fills the blanks.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from esb.crm import llm
from esb.crm.leadgen import compose
from esb.crm.leadgen.templates import (
    DEFAULT_DOCS, DOCUMENT_CATALOG, LIVE_STATUSES, MAX_TOUCH, SIGNATURE, TOUCH_BY_N, signature_for,
)
from esb.models.crm import CrmDistrict, CrmDossier, CrmPerson, CrmSequence, CrmSignal

_CATALOG_STR = "\n".join(f"- {t}: {w}" for t, w in DOCUMENT_CATALOG)


def now() -> datetime:
    return datetime.now(timezone.utc)


EXTRACT_SYS = """You prepare the variables for an outreach email to a school
district leader, in AJ Crabill's voice (first person, warm, direct, concrete), for
Effective School Boards — board coaching focused on student outcomes. Never invent
events. Return JSON with these keys:

- why_sentence: ONE complete, grammatical sentence explaining why AJ is reaching
  out, to appear right after "May I send you our free guidance document on X?".
  • If the DOSSIER or TRIGGER contains a specific, verifiable detail (a leadership
    change, a board initiative, recent news), reference it concretely and honestly —
    you may say you've been following developments at the district. Weave in the
    district's size only if it reads naturally.
  • If nothing specific is available, write a warm, generic reason that does NOT
    claim to have followed them and invents nothing (e.g. why ESB reaches out to
    boards like theirs).
- document: the best-fit guidance document — use the EXACT title from the DOCUMENT
  CATALOG provided below. Match it to the situation; default to "Effective Strategic
  Planning" or "Effective Goal Monitoring" only when nothing specific fits.
- alt_document: a different, also-relevant title from the catalog.
- governance_challenge: a short noun phrase (e.g. "a leadership transition").
- trigger_brief: a 3-6 word reference to the situation.
- governance_topic: a short topic phrase."""

_HONORIFICS = {"dr", "dr.", "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "mx", "mx.",
               "hon", "hon.", "rev", "rev.", "prof", "prof.", "the"}


def first_name(name: str) -> str:
    for tok in (name or "").split():
        if tok.lower().strip(".") not in {h.strip(".") for h in _HONORIFICS}:
            return tok.rstrip(",")
    return "there"


def extract_vars(session: Session, person: CrmPerson, district: CrmDistrict | None) -> dict:
    first = first_name(person.name)
    dn = district.name if district else "your district"
    base = {
        "first_name": first, "district_name": dn,
        "document": DEFAULT_DOCS[0], "alt_document": DEFAULT_DOCS[1],
        "governance_challenge": "the competing demands on a board's attention",
        "trigger_brief": "your board's current priorities",
        "governance_topic": "governing toward student outcomes",
        "why_sentence": (f"I'm reaching out because Effective School Boards helps boards "
                         f"like {dn}'s keep their focus on the outcomes that matter most "
                         f"for students."),
    }
    if not llm.configured():
        return base
    dossier = session.execute(
        select(CrmDossier).where(CrmDossier.person_id == person.id).order_by(CrmDossier.updated_at.desc())
    ).scalars().first()
    sig = None
    if district:
        sig = session.execute(
            select(CrmSignal).where(CrmSignal.district_id == district.id).order_by(CrmSignal.detected_at.desc())
        ).scalars().first()
    trigger = (district.context if district and district.context
               else (sig.headline if sig else ""))
    ctx = "\n".join(filter(None, [
        f"Recipient: {person.name}, {person.role} at {dn}",
        f"District size: {district.enrollment:,} students" if district and district.enrollment else "",
        f"Dossier: {dossier.summary}" if dossier and dossier.summary else "",
        f"CURRENT GOVERNANCE CONTEXT: {trigger}" if trigger else "CURRENT GOVERNANCE CONTEXT: none",
        f"\nDOCUMENT CATALOG (choose document/alt_document from these exact titles):\n{_CATALOG_STR}",
    ]))
    try:
        out = llm.complete_json_sync(EXTRACT_SYS, ctx, max_tokens=500)
        for k in ("why_sentence", "document", "alt_document", "governance_challenge",
                  "trigger_brief", "governance_topic"):
            if out.get(k):
                base[k] = str(out[k]).strip()
    except Exception:
        pass
    return base


def ensure_sequence(session: Session, person: CrmPerson, email: str, district: CrmDistrict | None) -> CrmSequence:
    seq = session.execute(
        select(CrmSequence).where(CrmSequence.person_id == person.id)
    ).scalars().first()
    if seq:
        return seq
    seq = CrmSequence(person_id=person.id, email=email, status="not_contacted",
                      current_touch=0, next_due_at=now(),
                      vars=extract_vars(session, person, district))
    session.add(seq)
    session.commit()
    return seq


def due_touch(seq: CrmSequence) -> int | None:
    if seq.status not in LIVE_STATUSES or seq.current_touch >= MAX_TOUCH:
        return None
    if seq.next_due_at and seq.next_due_at > now():
        return None
    return seq.current_touch + 1


_ALL_VARS = ("first_name", "district_name", "why_sentence", "document",
             "alt_document", "governance_challenge", "trigger_brief", "governance_topic")


def render_touch(seq: CrmSequence, touch_n: int) -> tuple[str, str]:
    t = TOUCH_BY_N[touch_n]
    v = dict(seq.vars or {})
    body = t["body"].format(**{k: v.get(k, "") for k in _ALL_VARS})
    body = body.replace(SIGNATURE, signature_for(touch_n))
    return t["subject"], body + compose._footer(seq.email)


def advance_after_send(seq: CrmSequence, touch_n: int, sent_at: datetime) -> None:
    seq.current_touch = touch_n
    seq.last_sent_at = sent_at
    if touch_n >= MAX_TOUCH:
        seq.status, seq.next_due_at = "done", None
    else:
        seq.status = "email_sent"
        seq.next_due_at = sent_at + timedelta(days=TOUCH_BY_N[touch_n + 1]["interval_days"])
