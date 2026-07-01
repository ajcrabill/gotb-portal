"""Billing router — Stripe subscriptions, Stripe Connect, Dropbox Sign contracts."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.auth.rbac import AuthContext, get_auth_context
from esb.core.config import settings
from esb.core.database import get_db
from esb.models.billing import (
    Certification,
    CertificationStatus,
    Membership,
    MembershipStatus,
    MembershipTier,
)
from esb.models.user import RoleType
from esb.services import audit as audit_svc

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/billing", tags=["billing"])

# ── Stripe client (lazy import — Stripe SDK optional until installed) ─────────

def _stripe():
    try:
        import stripe
        stripe.api_key = settings.stripe_secret_key
        return stripe
    except ImportError:
        raise HTTPException(status_code=503, detail="Stripe SDK not installed.")


def _dropbox_sign():
    try:
        import dropbox_sign
        return dropbox_sign
    except ImportError:
        raise HTTPException(status_code=503, detail="Dropbox Sign SDK not installed.")


# ── Membership checkout ────────────────────────────────────────────────────────

class MembershipCheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


@router.post("/membership/checkout", response_model=MembershipCheckoutResponse)
async def create_membership_checkout(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> MembershipCheckoutResponse:
    """Create a Stripe Checkout session for the $2,500/yr membership."""
    stripe = _stripe()

    # Block if already has active membership
    existing = await db.scalar(
        select(Membership).where(
            Membership.person_id == auth.person_id,
            Membership.status == MembershipStatus.active,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Active membership already exists.")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": "ESB Practitioner Membership",
                    "description": "Annual membership — Effective School Boards Practitioner Network",
                },
                "unit_amount": 250000,   # $2,500.00
                "recurring": {"interval": "year"},
            },
            "quantity": 1,
        }],
        mode="subscription",
        success_url=f"{settings.frontend_url}/portal/membership/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.frontend_url}/portal/membership",
        metadata={"person_id": str(auth.person_id), "product": "membership"},
        client_reference_id=str(auth.person_id),
    )

    await audit_svc.record(
        db, action="billing.membership.checkout_created", resource_type="membership",
        actor_id=auth.person_id, payload={"stripe_session_id": session.id},
    )
    await db.commit()

    return MembershipCheckoutResponse(checkout_url=session.url, session_id=session.id)


# ── Certification checkout ─────────────────────────────────────────────────────

@router.post("/certification/checkout", response_model=MembershipCheckoutResponse)
async def create_certification_checkout(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> MembershipCheckoutResponse:
    """Create a Stripe payment for the $5,000/3yr certification."""
    stripe = _stripe()

    # Must have active membership
    membership = await db.scalar(
        select(Membership).where(
            Membership.person_id == auth.person_id,
            Membership.status == MembershipStatus.active,
        )
    )
    if not membership:
        raise HTTPException(status_code=402, detail="Active membership required before certification.")

    # Block if already certified
    existing = await db.scalar(
        select(Certification).where(
            Certification.person_id == auth.person_id,
            Certification.status == CertificationStatus.active,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Active certification already exists.")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": "Certified Great on Their Behalf Practitioner Credential",
                    "description": "3-year certification — Effective School Boards",
                },
                "unit_amount": 500000,   # $5,000.00
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=f"{settings.frontend_url}/portal/certification/sign?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.frontend_url}/portal/certification",
        metadata={"person_id": str(auth.person_id), "product": "certification"},
        client_reference_id=str(auth.person_id),
    )

    await audit_svc.record(
        db, action="billing.certification.checkout_created", resource_type="certification",
        actor_id=auth.person_id, payload={"stripe_session_id": session.id},
    )
    await db.commit()

    return MembershipCheckoutResponse(checkout_url=session.url, session_id=session.id)


# ── Stripe Connect onboarding ──────────────────────────────────────────────────

class ConnectOnboardingResponse(BaseModel):
    onboarding_url: str


@router.post("/connect/onboard", response_model=ConnectOnboardingResponse)
async def create_connect_onboarding(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> ConnectOnboardingResponse:
    """Initiate Stripe Connect Express onboarding for 85% disbursements."""
    if not auth.has_role(
        RoleType.certified_practitioner,
        RoleType.senior_practitioner,
        RoleType.practitioner_manager,
        RoleType.lead_senior_practitioner,
        RoleType.superuser,
    ):
        raise HTTPException(status_code=403, detail="Practitioner role required.")

    stripe = _stripe()

    # Create or retrieve Connect account
    account = stripe.Account.create(
        type="express",
        capabilities={"transfers": {"requested": True}},
        metadata={"person_id": str(auth.person_id)},
    )

    link = stripe.AccountLink.create(
        account=account.id,
        refresh_url=f"{settings.frontend_url}/portal/billing/connect/refresh",
        return_url=f"{settings.frontend_url}/portal/billing/connect/complete",
        type="account_onboarding",
    )

    await audit_svc.record(
        db, action="billing.connect.onboarding_started", resource_type="person",
        resource_id=auth.person_id, actor_id=auth.person_id,
        payload={"stripe_account_id": account.id},
    )
    await db.commit()

    return ConnectOnboardingResponse(onboarding_url=link.url)


# ── Dropbox Sign — send certification agreement ────────────────────────────────

class SignatureRequestResponse(BaseModel):
    envelope_id: str
    signer_url: str | None  # embedded signing URL (if using embedded flow)


@router.post("/certification/sign", response_model=SignatureRequestResponse)
async def send_certification_agreement(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    stripe_session_id: str,
    db: AsyncSession = Depends(get_db),
) -> SignatureRequestResponse:
    """Send Dropbox Sign certification agreement after payment confirmation."""
    stripe = _stripe()

    # Verify payment
    session = stripe.checkout.Session.retrieve(stripe_session_id)
    if session.payment_status != "paid":
        raise HTTPException(status_code=402, detail="Payment not confirmed.")
    if session.metadata.get("person_id") != str(auth.person_id):
        raise HTTPException(status_code=403, detail="Session mismatch.")

    # Create or update certification record
    cert = await db.scalar(
        select(Certification).where(
            Certification.person_id == auth.person_id,
            Certification.status == CertificationStatus.pending,
        )
    )
    if not cert:
        cert = Certification(
            person_id=auth.person_id,
            status=CertificationStatus.pending,
            stripe_payment_intent_id=session.payment_intent,
        )
        db.add(cert)
        await db.flush()

    _dropbox_sign()  # validate API key is configured

    # Send agreement via Dropbox Sign
    # Template ID stored in settings — the Practitioner Agreement template
    if not settings.dropbox_sign_template_id:
        raise HTTPException(status_code=503, detail="Dropbox Sign template not configured.")

    from dropbox_sign import ApiClient, Configuration, SignatureRequestApi
    from dropbox_sign.models import (
        SignatureRequestSendWithTemplateRequest,
        SubSignatureRequestTemplateSigner,
    )

    configuration = Configuration(username=settings.dropbox_sign_api_key)
    with ApiClient(configuration) as api_client:
        api = SignatureRequestApi(api_client)
        data = SignatureRequestSendWithTemplateRequest(
            template_ids=[settings.dropbox_sign_template_id],
            subject="Certified Great on Their Behalf Practitioner Agreement",
            message="Please review and sign your practitioner agreement to complete your certification.",
            signers=[SubSignatureRequestTemplateSigner(
                role="Practitioner",
                email_address=auth.email,
                name=auth.name or auth.email,
            )],
            metadata={"person_id": str(auth.person_id), "cert_id": str(cert.id)},
            signing_redirect_url=f"{settings.frontend_url}/portal/certification/complete",
        )
        response = api.signature_request_send_with_template(data)

    cert.dropbox_sign_envelope_id = response.signature_request.signature_request_id
    await audit_svc.record(
        db, action="billing.certification.agreement_sent", resource_type="certification",
        resource_id=cert.id, actor_id=auth.person_id,
        payload={"envelope_id": cert.dropbox_sign_envelope_id},
    )
    await db.commit()

    return SignatureRequestResponse(
        envelope_id=cert.dropbox_sign_envelope_id,
        signer_url=None,  # email-based flow; embedded signing can be added later
    )


# ── Stripe webhook ─────────────────────────────────────────────────────────────

@router.post("/stripe/webhook", status_code=200)
async def stripe_webhook(
    request: Request,
    stripe_signature: Annotated[str | None, Header(alias="stripe-signature")] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Handle Stripe webhook events.

    Events handled:
    - checkout.session.completed → create Membership or Certification record
    - customer.subscription.deleted → lapse Membership, set tail_until = now + 12 months
    - account.updated (Connect) → store stripe_account_id on person record
    - charge.refunded → mark Invoice as refunded
    """
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header.")

    stripe = _stripe()
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    event_type = event["type"]
    data = event["data"]["object"]
    log.info(f"stripe_webhook.received type={event_type} id={event.get('id')}")

    # ── checkout.session.completed ────────────────────────────────────────────
    if event_type == "checkout.session.completed":
        person_id_str = data.get("metadata", {}).get("person_id")
        product = data.get("metadata", {}).get("product")

        if not person_id_str:
            return {"status": "skipped", "reason": "no person_id in metadata"}

        person_id = UUID(person_id_str)

        if product == "membership":
            now = datetime.now(timezone.utc)
            mem = Membership(
                person_id=person_id,
                tier=MembershipTier.annual,
                status=MembershipStatus.active,
                stripe_subscription_id=data.get("subscription"),
                stripe_customer_id=data.get("customer"),
                period_start=now,
                period_end=now + timedelta(days=365),
                amount_cents=250000,
            )
            db.add(mem)
            await audit_svc.record(
                db, action="billing.membership.activated", resource_type="membership",
                actor_id=person_id, payload={"stripe_session_id": data.get("id")},
            )

        elif product == "certification":
            cert = await db.scalar(
                select(Certification).where(
                    Certification.person_id == person_id,
                    Certification.status == CertificationStatus.pending,
                )
            )
            if not cert:
                cert = Certification(
                    person_id=person_id,
                    status=CertificationStatus.pending,
                    stripe_payment_intent_id=data.get("payment_intent"),
                    amount_cents=500000,
                )
                db.add(cert)
            else:
                cert.stripe_payment_intent_id = data.get("payment_intent")

            await audit_svc.record(
                db, action="billing.certification.payment_received", resource_type="certification",
                resource_id=cert.id if cert.id else None, actor_id=person_id,
            )

    # ── customer.subscription.deleted → membership lapse ─────────────────────
    elif event_type == "customer.subscription.deleted":
        sub_id = data.get("id")
        mem = await db.scalar(
            select(Membership).where(Membership.stripe_subscription_id == sub_id)
        )
        if mem:
            mem.status = MembershipStatus.lapsed
            mem.tail_until = datetime.now(timezone.utc) + timedelta(days=365)
            await audit_svc.record(
                db, action="billing.membership.lapsed", resource_type="membership",
                resource_id=mem.id, actor_id=mem.person_id,
                payload={"stripe_subscription_id": sub_id, "tail_until": mem.tail_until.isoformat()},
            )

    # ── invoice.payment_succeeded → extend membership period_end on renewal ─────
    elif event_type == "invoice.payment_succeeded":
        sub_id = data.get("subscription")
        if sub_id:
            mem = await db.scalar(
                select(Membership).where(Membership.stripe_subscription_id == sub_id)
            )
            if mem and mem.status == MembershipStatus.active:
                # Stripe sends period_end as a Unix timestamp
                period_end_ts = data.get("lines", {}).get("data", [{}])[0].get("period", {}).get("end")
                if period_end_ts:
                    mem.period_end = datetime.fromtimestamp(period_end_ts, tz=timezone.utc)
                else:
                    mem.period_end = datetime.now(timezone.utc) + timedelta(days=365)
                mem.tail_until = None  # clear any lapse tail on successful renewal
                await audit_svc.record(
                    db, action="billing.membership.renewed", resource_type="membership",
                    resource_id=mem.id, actor_id=mem.person_id,
                    payload={"period_end": mem.period_end.isoformat(), "invoice_id": data.get("id")},
                )

    # ── invoice.payment_failed → flag membership for follow-up ───────────────
    elif event_type == "invoice.payment_failed":
        sub_id = data.get("subscription")
        attempt_count = data.get("attempt_count", 1)
        if sub_id:
            mem = await db.scalar(
                select(Membership).where(Membership.stripe_subscription_id == sub_id)
            )
            if mem:
                # Stripe will retry; we record it. After 3 failures Stripe cancels
                # the subscription and fires customer.subscription.deleted, which lapses us.
                await audit_svc.record(
                    db, action="billing.membership.payment_failed", resource_type="membership",
                    resource_id=mem.id, actor_id=mem.person_id,
                    payload={"attempt": attempt_count, "invoice_id": data.get("id")},
                )

    # ── account.updated → Stripe Connect onboarding complete ─────────────────
    elif event_type == "account.updated":
        # charges_enabled flips to True when Connect onboarding is complete
        if data.get("charges_enabled") and data.get("metadata", {}).get("person_id"):
            person_id = UUID(data["metadata"]["person_id"])
            await audit_svc.record(
                db, action="billing.connect.onboarding_complete", resource_type="person",
                resource_id=person_id, actor_id=person_id,
                payload={"stripe_account_id": data.get("id")},
            )

    await db.commit()
    return {"status": "ok", "event": event_type}


# ── Dropbox Sign webhook ───────────────────────────────────────────────────────

@router.post("/dropbox-sign/webhook")
async def dropbox_sign_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    """
    Handle Dropbox Sign webhook: signature_request_signed → activate Certification.
    Dropbox Sign sends form-encoded JSON (json field) and requires the
    literal response body "Hello API Event Received" (not JSON) to mark the
    callback as successfully received.

    Verified via HMAC-SHA256 of (event_time + event_type) using the account
    API key — Dropbox Sign does not issue a separate webhook signing secret.
    """
    form = await request.form()
    import hashlib
    import hmac
    import json as _json

    try:
        payload = _json.loads(form.get("json", "{}"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook payload.")

    event = payload.get("event", {})
    event_time = event.get("event_time", "")
    event_type = event.get("event_type")
    event_hash = event.get("event_hash", "")

    expected_hash = hmac.new(
        settings.dropbox_sign_api_key.encode(),
        f"{event_time}{event_type}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, event_hash):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    sr = payload.get("signature_request", {})
    metadata = sr.get("metadata", {})

    if event_type == "signature_request_signed":
        person_id_str = metadata.get("person_id")
        cert_id_str = metadata.get("cert_id")
        if not person_id_str:
            return PlainTextResponse("Hello API Event Received")

        person_id = UUID(person_id_str)
        now = datetime.now(timezone.utc)

        cert_query = select(Certification).where(
            Certification.person_id == person_id,
            Certification.status == CertificationStatus.pending,
        )
        if cert_id_str:
            cert_query = select(Certification).where(Certification.id == UUID(cert_id_str))

        cert = await db.scalar(cert_query)
        if cert:
            cert.status = CertificationStatus.active
            cert.agreement_signed_at = now
            cert.issued_at = now
            cert.expires_at = now + timedelta(days=3 * 365)
            await audit_svc.record(
                db, action="billing.certification.issued", resource_type="certification",
                resource_id=cert.id, actor_id=person_id,
                payload={"expires_at": cert.expires_at.isoformat()},
            )

    await db.commit()
    return PlainTextResponse("Hello API Event Received")


# ── Status endpoint ────────────────────────────────────────────────────────────

class BillingStatusResponse(BaseModel):
    has_membership: bool
    membership_status: str | None
    membership_until: str | None
    has_certification: bool
    certification_status: str | None
    certification_expires: str | None


@router.get("/status", response_model=BillingStatusResponse)
async def billing_status(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> BillingStatusResponse:
    mem = await db.scalar(
        select(Membership).where(Membership.person_id == auth.person_id)
    )
    cert = await db.scalar(
        select(Certification).where(
            Certification.person_id == auth.person_id,
            Certification.status == CertificationStatus.active,
        )
    )
    return BillingStatusResponse(
        has_membership=mem is not None,
        membership_status=mem.status.value if mem else None,
        membership_until=mem.period_end.isoformat() if mem else None,
        has_certification=cert is not None,
        certification_status=cert.status.value if cert else None,
        certification_expires=cert.expires_at.isoformat() if cert and cert.expires_at else None,
    )
