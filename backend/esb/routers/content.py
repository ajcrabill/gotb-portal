"""Content Approval router — proxies to esby-portal's content pipeline admin API.

Interim architecture: esby-portal (on esbcloud) hosts the actual content
generation/publish engine (site-pipeline: LLM generation, GitHub pushes,
rescind). This router is a thin, RBAC-gated proxy so the review/approval
workflow lives natively in the portal without duplicating that fragile
subprocess+GitHub logic. Access: lead_senior_practitioner, content_manager,
superuser.
"""
from __future__ import annotations

from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from esb.auth.rbac import AuthContext, get_auth_context
from esb.core.config import settings
from esb.models.user import RoleType

router = APIRouter(prefix="/api/content", tags=["content"])

CONTENT_ROLES = {
    RoleType.lead_senior_practitioner,
    RoleType.content_manager,
    RoleType.superuser,
}


def _require_content_access(auth: AuthContext) -> None:
    if not auth.has_role(*CONTENT_ROLES):
        raise HTTPException(status_code=403, detail="Content approval access required.")


async def _upstream(method: str, path: str, **kwargs: Any) -> httpx.Response:
    if not settings.esby_internal_key:
        raise HTTPException(status_code=503, detail="Content pipeline bridge not configured.")
    async with httpx.AsyncClient(timeout=30.0) as client:
        return await client.request(
            method,
            f"{settings.esby_internal_url}/admin{path}",
            headers={"X-Internal-Key": settings.esby_internal_key},
            **kwargs,
        )


def _relay(resp: httpx.Response) -> Any:
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise HTTPException(status_code=resp.status_code, detail=detail)
    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()


# ── Drafts ───────────────────────────────────────────────────────────────────

@router.get("/drafts")
async def list_drafts(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    status: str = "pending",
) -> Any:
    _require_content_access(auth)
    return _relay(await _upstream("GET", "/api/drafts", params={"status": status}))


@router.get("/draft/{draft_id}")
async def get_draft(
    draft_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> Any:
    _require_content_access(auth)
    return _relay(await _upstream("GET", f"/api/draft/{draft_id}"))


@router.put("/draft/{draft_id}")
async def update_draft(
    draft_id: str,
    body: dict,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> Any:
    _require_content_access(auth)
    return _relay(await _upstream("PUT", f"/api/draft/{draft_id}", json=body))


@router.post("/draft/{draft_id}/approve")
async def approve_draft(
    draft_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> Any:
    _require_content_access(auth)
    return _relay(await _upstream("POST", f"/api/draft/{draft_id}/approve"))


@router.post("/draft/{draft_id}/reject")
async def reject_draft(
    draft_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> Any:
    _require_content_access(auth)
    return _relay(await _upstream("POST", f"/api/draft/{draft_id}/reject"))


@router.post("/draft/{draft_id}/mark-reviewed")
async def mark_reviewed(
    draft_id: str,
    body: dict,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> Any:
    _require_content_access(auth)
    return _relay(await _upstream("POST", f"/api/draft/{draft_id}/mark-reviewed", json=body))


@router.post("/draft/{draft_id}/reviewer-notes")
async def set_reviewer_notes(
    draft_id: str,
    body: dict,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> Any:
    _require_content_access(auth)
    return _relay(await _upstream("POST", f"/api/draft/{draft_id}/reviewer-notes", json=body))


@router.post("/draft/{draft_id}/rescind")
async def rescind_draft(
    draft_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> Any:
    _require_content_access(auth)
    return _relay(await _upstream("POST", f"/api/draft/{draft_id}/rescind"))


# ── Sites ────────────────────────────────────────────────────────────────────

@router.get("/sites")
async def list_sites(auth: Annotated[AuthContext, Depends(get_auth_context)]) -> Any:
    _require_content_access(auth)
    return _relay(await _upstream("GET", "/api/sites"))


@router.put("/sites/{site_id}")
async def update_site(
    site_id: str,
    body: dict,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> Any:
    _require_content_access(auth)
    return _relay(await _upstream("PUT", f"/api/sites/{site_id}", json=body))


@router.post("/sites/{site_id}/trigger")
async def trigger_site(
    site_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> Any:
    _require_content_access(auth)
    return _relay(await _upstream("POST", f"/api/sites/{site_id}/trigger"))


# ── Guides ───────────────────────────────────────────────────────────────────

@router.get("/guides")
async def list_guides(auth: Annotated[AuthContext, Depends(get_auth_context)]) -> Any:
    _require_content_access(auth)
    return _relay(await _upstream("GET", "/api/guides"))


@router.get("/guide/{site_id}")
async def get_guide(
    site_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> Any:
    _require_content_access(auth)
    return _relay(await _upstream("GET", f"/api/guide/{site_id}"))


# ── Newsletters ──────────────────────────────────────────────────────────────

@router.get("/newsletters")
async def list_newsletters(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    status: str = "pending",
) -> Any:
    _require_content_access(auth)
    return _relay(await _upstream("GET", "/api/newsletters", params={"status": status}))


@router.post("/newsletter/{draft_id}/approve")
async def approve_newsletter(
    draft_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> Any:
    _require_content_access(auth)
    return _relay(await _upstream("POST", f"/api/newsletter/{draft_id}/approve"))


@router.post("/newsletter/{draft_id}/reject")
async def reject_newsletter(
    draft_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> Any:
    _require_content_access(auth)
    return _relay(await _upstream("POST", f"/api/newsletter/{draft_id}/reject"))


# ── Weights (legacy coaching-criteria rubric — distinct from the live
#    ScoringConfig used by assessments; ported as-is, not wired to scoring) ──

@router.get("/weights")
async def list_weights(auth: Annotated[AuthContext, Depends(get_auth_context)]) -> Any:
    _require_content_access(auth)
    return _relay(await _upstream("GET", "/api/weights"))


@router.put("/weights/{criterion_key}")
async def update_weight(
    criterion_key: str,
    body: dict,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> Any:
    _require_content_access(auth)
    return _relay(await _upstream("PUT", f"/api/weights/{criterion_key}", json=body))
