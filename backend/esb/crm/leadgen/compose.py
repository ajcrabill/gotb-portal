"""Compose a compliant, personalized outreach email.

Ported from coach-devon's leadgen/compose.py. CAN-SPAM: every body gets a
physical postal address and a working one-click unsubscribe.
"""
from __future__ import annotations

import html as _html
import re

from itsdangerous import URLSafeSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from esb.core.config import settings
from esb.crm import llm
from esb.models.crm import CrmDistrict, CrmDossier, CrmGlobalDirective, CrmPerson, CrmSignal, CrmVoiceSample

_serializer = URLSafeSerializer(settings.secret_key, salt="unsubscribe")

DEFAULT_TEMPLATE = (
    "Dear {salutation},\n\n"
    "{snippet}\n\n"
    "At Effective School Boards, we help boards like {district}'s focus on the "
    "outcomes that matter most for students. I'd welcome a brief conversation "
    "about how your board governs toward student achievement.\n\n"
    "Best regards,\n{sender_name}"
)
DEFAULT_SUBJECT = "Supporting the {district} board's focus on students"

PERSONALIZE_SYS = (
    "Write ONE warm, specific opening sentence for an outreach email to a school "
    "board member or superintendent, referencing their district's current situation "
    "without being presumptuous or negative. Return JSON: {\"snippet\":\"...\"}."
)


def unsubscribe_token(email: str) -> str:
    return _serializer.dumps(email)


def email_from_token(token: str) -> str | None:
    try:
        return _serializer.loads(token)
    except Exception:
        return None


def unsub_url(token: str) -> str:
    return f"{settings.unsubscribe_base_url}/api/crm/leadgen/unsubscribe/{token}"


def _salutation(person: CrmPerson) -> str:
    role = "Superintendent" if person.role == "superintendent" else "Board Member"
    return f"{role} {person.name.split()[-1]}" if person.name else role


def personalize(session: Session, person: CrmPerson, district: CrmDistrict | None) -> str:
    sig = None
    if district:
        sig = session.execute(
            select(CrmSignal).where(CrmSignal.district_id == district.id)
            .order_by(CrmSignal.detected_at.desc())
        ).scalars().first()

    if llm.configured() and district:
        ctx = f"district: {district.name}, {district.state}\nrole: {person.role}"
        if sig:
            ctx += f"\nrecent news: {sig.headline}"
        try:
            return llm.complete_json_sync(PERSONALIZE_SYS, ctx).get("snippet", "").strip()
        except Exception:
            pass

    if sig:
        return (f"I've been following developments around {district.name} and "
                f"the board's work, and I believe ESB could be a helpful partner.")
    dn = district.name if district else "your district"
    return f"I'm reaching out because of the important governance work underway at {dn}."


_FOOTER_SEP = "\n\n—\n"


def _footer(email: str) -> str:
    addr = settings.esb_postal_address or "[ESB postal address not configured]"
    return (f"{_FOOTER_SEP}Effective School Boards · {addr}\n"
            f"If you'd prefer I not email you, click here.")


_URL_RE = re.compile(r"(https?://[^\s<]+)")
_UNSUB_TEXT = "click here."


def _esc(text: str, unsub_url: str) -> str:
    e = _html.escape(text)
    e = _URL_RE.sub(r'<a href="\1">\1</a>', e)
    e = e.replace(_UNSUB_TEXT, f'click <a href="{unsub_url}">here</a>.')
    return e.replace("\n", "<br>\n")


def to_parts(body: str, unsub_url: str) -> tuple[str, str]:
    plain = body.replace(_UNSUB_TEXT, f"to unsubscribe, visit: {unsub_url}")
    main, sep, footer = body.partition(_FOOTER_SEP)
    html = (f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;'
            f'color:#222">{_esc(main, unsub_url)}')
    if footer:
        html += (f'<div style="font-size:11px;color:#999;margin-top:14px">—<br>\n'
                 f'{_esc(footer, unsub_url)}</div>')
    html += "</div>"
    return plain, html


COMPOSE_SYS = (
    "You are AJ Crabill writing a short, warm, specific outreach email to a school "
    "superintendent or board member about Effective School Boards (ESB), which coaches "
    "boards to focus on student outcomes. Match the VOICE of the provided samples exactly. "
    "Be concrete about the recipient and their district; never generic or salesy; no "
    "emojis. Follow every standing directive. Return JSON: "
    "{\"subject\":\"...\",\"body\":\"...(no signature footer)\",\"rationale\":\"one line: why this person now\"}."
)


def compose_email(session: Session, person: CrmPerson, district: CrmDistrict | None, email: str) -> tuple[str, str, str]:
    """Full email in AJ's voice using the person's dossier + district signal +
    voice samples + standing directives. Falls back to the template if the LLM is off."""
    dossier = session.execute(
        select(CrmDossier).where(CrmDossier.person_id == person.id).order_by(CrmDossier.updated_at.desc())
    ).scalars().first()
    sig = None
    if district:
        sig = session.execute(
            select(CrmSignal).where(CrmSignal.district_id == district.id).order_by(CrmSignal.detected_at.desc())
        ).scalars().first()

    if llm.configured():
        role = "board_chair" if person.role != "superintendent" else "superintendent"
        samples = session.execute(
            select(CrmVoiceSample).where(CrmVoiceSample.role == role).limit(3)
        ).scalars().all()
        directives = session.execute(
            select(CrmGlobalDirective).where(CrmGlobalDirective.active.is_(True))
            .order_by(CrmGlobalDirective.id.desc()).limit(8)
        ).scalars().all()
        ctx = [
            f"RECIPIENT: {person.name} — {person.role} at {district.name if district else 'their district'}"
            f"{', ' + district.state if district else ''}",
            f"DOSSIER: {dossier.summary}" if dossier and dossier.summary else "DOSSIER: (none yet)",
            f"CURRENT NEWS/SIGNAL: {sig.headline}" if sig else "",
            "STANDING DIRECTIVES (follow these): " + (" | ".join(d.text for d in directives) if directives else "(none)"),
            "VOICE SAMPLES (match this style):",
            *[f"---\n{v.body[:1200]}" for v in samples],
        ]
        try:
            out = llm.complete_json_sync(COMPOSE_SYS, "\n".join(filter(None, ctx)), max_tokens=900)
            subject = (out.get("subject") or "").strip()
            body = (out.get("body") or "").strip()
            rationale = (out.get("rationale") or "").strip()
            if subject and body:
                return subject, body + _footer(email), rationale[:600]
        except Exception:
            pass

    snippet = personalize(session, person, district)
    fields = {"salutation": _salutation(person),
              "district": district.name if district else "your district",
              "snippet": snippet, "sender_name": settings.send_from_name}
    subject = DEFAULT_SUBJECT.format(**fields)
    body = DEFAULT_TEMPLATE.format(**fields, first_name="", role=person.role) + _footer(email)
    rationale = (sig.headline if sig else "round-robin outreach")[:600]
    return subject, body, rationale


def render(session: Session, campaign, person: CrmPerson, email: str) -> tuple[str, str]:
    district = session.get(CrmDistrict, person.district_id) if person.district_id else None
    snippet = personalize(session, person, district)
    fields = {
        "salutation": _salutation(person),
        "first_name": person.name.split()[0] if person.name else "",
        "district": district.name if district else "your district",
        "role": person.role,
        "snippet": snippet,
        "sender_name": settings.send_from_name,
    }
    subject = (campaign.subject or DEFAULT_SUBJECT).format(**fields)
    body = (campaign.template or DEFAULT_TEMPLATE).format(**fields)

    token = unsubscribe_token(email)
    unsub = f"{settings.unsubscribe_base_url}/api/crm/leadgen/unsubscribe/{token}"
    addr = settings.esb_postal_address or "[ESB postal address not configured]"
    body += (
        f"\n\n—\nEffective School Boards · {addr}\n"
        f"To stop receiving these emails, unsubscribe here: {unsub}"
    )
    return subject, body
