"""LeadGen orchestration — campaign building + cadence draft generation.

Ported from coach-devon's leadgen/run.py. The bulk Gmail-based send_campaign()
is not ported — Devon's own gmail.py send() unconditionally raises
NotConfigured (real OAuth wiring was never completed upstream). Both send
paths (per-message approve + bulk campaign send) are wired through the
portal's existing, working Postmark email service instead — see
esb/routers/leadgen.py.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from esb.crm.leadgen import cadence, compose
from esb.crm.studio import voice_lint
from esb.models.crm import CrmCampaign, CrmDistrict, CrmMessage, CrmPerson, CrmSequence, CrmSuppression


def _suppressed(session: Session, email: str) -> bool:
    return session.execute(
        select(CrmSuppression).where(CrmSuppression.email == email)
    ).scalar_one_or_none() is not None


def _continuous_campaign(session: Session) -> CrmCampaign:
    camp = session.execute(
        select(CrmCampaign).where(CrmCampaign.name == "Continuous Cadence")
    ).scalars().first()
    if not camp:
        camp = CrmCampaign(name="Continuous Cadence", status="built")
        session.add(camp)
        session.commit()
    return camp


def build_campaign(session: Session, campaign: CrmCampaign) -> dict:
    session.query(CrmMessage).filter(CrmMessage.campaign_id == campaign.id).delete()
    from esb.crm.leadgen.segment import resolve
    recipients = resolve(session, campaign.segment or {})
    counts = {"recipients": len(recipients), "queued": 0, "suppressed": 0}
    for person, email in recipients:
        if _suppressed(session, email):
            counts["suppressed"] += 1
            session.add(CrmMessage(campaign_id=campaign.id, person_id=person.id, email=email,
                                    status="skipped_suppressed"))
            continue
        subject, body = compose.render(session, campaign, person, email)
        session.add(CrmMessage(
            campaign_id=campaign.id, person_id=person.id, email=email,
            subject=subject, body=body, status="queued",
            unsubscribe_token=compose.unsubscribe_token(email),
            voice_flags=voice_lint(subject) + voice_lint(body),
        ))
        counts["queued"] += 1
    campaign.status = "built"
    session.commit()
    return counts


def _has_pending_draft(session: Session, sequence_id) -> bool:
    return session.execute(
        select(CrmMessage).where(CrmMessage.sequence_id == sequence_id, CrmMessage.status == "draft")
    ).scalars().first() is not None


def _best_email(session: Session, person: CrmPerson) -> str | None:
    from esb.models.crm import CrmEmail
    row = session.execute(
        select(CrmEmail).where(CrmEmail.person_id == person.id,
                                CrmEmail.status.in_(["verified", "web_confirmed"]))
        .limit(1)
    ).scalars().first()
    return row.email if row else None


def _draft_touch(session: Session, camp: CrmCampaign, seq: CrmSequence, touch_n: int) -> None:
    subject, body = cadence.render_touch(seq, touch_n)
    session.add(CrmMessage(
        campaign_id=camp.id, sequence_id=seq.id, touch_number=touch_n,
        person_id=seq.person_id, email=seq.email, subject=subject, body=body,
        status="draft", unsubscribe_token=compose.unsubscribe_token(seq.email),
        voice_flags=voice_lint(subject) + voice_lint(body),
    ))
    session.commit()


def generate_drafts(session: Session, count: int) -> int:
    camp = _continuous_campaign(session)
    made = 0

    live = session.execute(
        select(CrmSequence).where(CrmSequence.status.in_(["not_contacted", "email_sent"]),
                                   CrmSequence.next_due_at <= cadence.now())
        .order_by(CrmSequence.next_due_at).limit(count * 5)
    ).scalars().all()
    for seq in live:
        if made >= count:
            break
        tn = cadence.due_touch(seq)
        if tn is None or _has_pending_draft(session, seq.id):
            continue
        if _suppressed(session, seq.email):
            seq.status = "stopped"
            session.commit()
            continue
        _draft_touch(session, camp, seq, tn)
        made += 1

    have_seq = select(CrmSequence.person_id)
    candidates = session.execute(
        select(CrmPerson).join(CrmDistrict, CrmPerson.district_id == CrmDistrict.id)
        .where(CrmPerson.status == "current", CrmPerson.id.not_in(have_seq))
        .order_by(CrmDistrict.situation_score.desc(), CrmDistrict.enrollment.desc().nullslast())
        .limit(count * 25)
    ).scalars().all()
    for p in candidates:
        if made >= count:
            break
        email = _best_email(session, p)
        if not email or _suppressed(session, email):
            continue
        district = session.get(CrmDistrict, p.district_id) if p.district_id else None
        seq = cadence.ensure_sequence(session, p, email, district)
        if _has_pending_draft(session, seq.id):
            continue
        _draft_touch(session, camp, seq, 1)
        made += 1

    return made
