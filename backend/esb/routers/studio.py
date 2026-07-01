"""Studio — Governance Writer + Presentation Creator.

Ported natively from coach-devon's /governance/* and /presentation/* modules.
Access: lead_senior_practitioner only.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from esb.auth.rbac import AuthContext, get_auth_context
from esb.crm import studio
from esb.crm.llm import LLMUnavailable
from esb.models.user import RoleType

router = APIRouter(prefix="/api/crm/studio", tags=["crm-studio"])

CRM_ROLES = {RoleType.lead_senior_practitioner, RoleType.superuser}


def _require_crm_access(auth: AuthContext) -> None:
    if not auth.has_role(*CRM_ROLES):
        raise HTTPException(status_code=403, detail="CRM access required.")


class WriteRequest(BaseModel):
    purpose: str
    context: str = ""
    draft: str = ""


@router.post("/governance/write")
async def governance_write(
    body: WriteRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict:
    _require_crm_access(auth)
    try:
        return await studio.write(body.purpose, body.context, body.draft)
    except LLMUnavailable:
        raise HTTPException(status_code=503, detail="LLM not configured (OPENROUTER_API_KEY unset).")


class LintRequest(BaseModel):
    text: str


@router.post("/governance/lint")
async def governance_lint(
    body: LintRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict:
    _require_crm_access(auth)
    return {"voice_flags": studio.voice_lint(body.text)}


class OutlineRequest(BaseModel):
    topic: str


@router.post("/presentation/outline")
async def presentation_outline(
    body: OutlineRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict:
    _require_crm_access(auth)
    try:
        return await studio.generate_outline(body.topic)
    except LLMUnavailable:
        raise HTTPException(status_code=503, detail="LLM not configured — POST directly to /presentation/build instead.")


class DeckSpec(BaseModel):
    title: str
    subtitle: str = ""
    slides: list[dict] = []
    force: bool = False  # bypass the alignment gate after a human has reviewed the flags


@router.post("/presentation/build")
async def presentation_build(
    body: DeckSpec,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> Response:
    """Every slide's text is voice-linted before it's allowed into a deck —
    this runs even if the outline was hand-edited after /outline (or never
    went through /outline at all). Set force=true only after a human has
    reviewed the flags returned in the 422 response."""
    _require_crm_access(auth)
    spec = body.model_dump()
    flags = studio.lint_outline(spec)
    if flags and not body.force:
        raise HTTPException(status_code=422, detail={"message": "Alignment check found issues.", "voice_flags": flags})

    pptx_bytes = studio.build_deck(spec)
    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": 'attachment; filename="esb-deck.pptx"'},
    )
