"""Time Use Evaluation router — video submission, job status, repository.

Ported natively from esby-portal's /eval/* and /repository/* endpoints.
Access: all practitioner-tier roles.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.auth.rbac import AuthContext, get_auth_context
from esb.core.config import settings
from esb.core.database import get_db
from esb.eval.worker import process_job
from esb.models.eval import EvalBrokenReport, EvalJob
from esb.models.user import Person, RoleType

router = APIRouter(prefix="/api/eval", tags=["eval"])

PRACTITIONER_ROLES = {
    RoleType.certified_practitioner,
    RoleType.senior_practitioner,
    RoleType.practitioner_manager,
    RoleType.lead_senior_practitioner,
    RoleType.practitioner_in_training,
    RoleType.superuser,
}


def _require_practitioner(auth: AuthContext) -> None:
    if not auth.has_role(*PRACTITIONER_ROLES):
        raise HTTPException(status_code=403, detail="Practitioner role required.")


class EvalSubmit(BaseModel):
    video_url: str
    district_name: str | None = None
    meeting_date: str | None = None
    meeting_type: str = "Regular Board Meeting"
    review_span: str = "1_meeting"


class JobOut(BaseModel):
    id: str
    status: str
    video_url: str
    district_name: str | None
    meeting_date: str | None
    meeting_type: str | None
    review_span: str
    result_url: str | None
    error_msg: str | None
    meetings_analyzed: int | None
    created_at: str
    updated_at: str


def _job_out(job: EvalJob) -> JobOut:
    return JobOut(
        id=str(job.id), status=job.status, video_url=job.video_url,
        district_name=job.district_name, meeting_date=job.meeting_date,
        meeting_type=job.meeting_type, review_span=job.review_span,
        result_url=job.result_url, error_msg=job.error_msg,
        meetings_analyzed=job.meetings_analyzed,
        created_at=job.created_at.isoformat(), updated_at=job.updated_at.isoformat(),
    )


# ── Submission ───────────────────────────────────────────────────────────────

@router.post("/submit")
async def submit_eval(
    body: EvalSubmit,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_practitioner(auth)
    now = datetime.datetime.now(datetime.timezone.utc)
    job = EvalJob(
        person_id=auth.person_id,
        video_url=body.video_url,
        district_name=body.district_name,
        meeting_date=body.meeting_date,
        meeting_type=body.meeting_type,
        review_span=body.review_span or "1_meeting",
        status="pending",
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    await db.commit()

    import asyncio
    asyncio.get_event_loop().create_task(process_job(job.id))

    return {"job_id": str(job.id)}


@router.get("/status/{job_id}", response_model=JobOut)
async def eval_status(
    job_id: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> JobOut:
    _require_practitioner(auth)
    job = await db.scalar(
        select(EvalJob).where(EvalJob.id == job_id, EvalJob.person_id == auth.person_id)
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _job_out(job)


@router.get("/jobs", response_model=list[JobOut])
async def list_my_jobs(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> list[JobOut]:
    _require_practitioner(auth)
    rows = await db.scalars(
        select(EvalJob)
        .where(EvalJob.person_id == auth.person_id, EvalJob.hidden.is_(False))
        .order_by(EvalJob.created_at.desc())
        .limit(50)
    )
    return [_job_out(j) for j in rows.all()]


@router.delete("/jobs/{job_id}", status_code=204, response_model=None)
async def hide_my_job(
    job_id: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> None:
    _require_practitioner(auth)
    job = await db.get(EvalJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.person_id != auth.person_id:
        raise HTTPException(status_code=403, detail="Not your job.")
    job.hidden = True
    await db.commit()


@router.get("/download/{filename}")
async def eval_download(
    filename: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    _require_practitioner(auth)
    safe = Path(filename).name
    path = Path(settings.eval_docs_dir) / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    job = await db.scalar(
        select(EvalJob).where(EvalJob.result_file == str(path), EvalJob.person_id == auth.person_id)
    )
    if not job:
        raise HTTPException(status_code=403, detail="Access denied.")
    return FileResponse(
        str(path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=safe,
    )


# ── Repository (cross-practitioner index of completed evaluations) ─────────────

class RepositoryEntryOut(BaseModel):
    id: str
    district_name: str | None
    meeting_date: str | None
    meeting_type: str | None
    result_url: str | None
    created_at: str
    submitted_by: str


@router.get("/repository", response_model=list[RepositoryEntryOut])
async def repository(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> list[RepositoryEntryOut]:
    _require_practitioner(auth)
    rows = await db.execute(
        select(EvalJob, Person.email)
        .join(Person, Person.id == EvalJob.person_id, isouter=True)
        .where(EvalJob.status == "complete")
        .order_by(EvalJob.created_at.desc())
        .limit(200)
    )
    return [
        RepositoryEntryOut(
            id=str(job.id), district_name=job.district_name, meeting_date=job.meeting_date,
            meeting_type=job.meeting_type, result_url=job.result_url,
            created_at=job.created_at.isoformat(), submitted_by=email or str(job.person_id),
        )
        for job, email in rows.all()
    ]


@router.post("/repository/report/{job_id}")
async def report_broken(
    job_id: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    _require_practitioner(auth)
    job = await db.get(EvalJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    file_missing = not job.result_file or not Path(job.result_file).exists()
    db.add(EvalBrokenReport(
        job_id=job_id, reporter_id=auth.person_id,
        reported_at=datetime.datetime.now(datetime.timezone.utc),
        file_exists=not file_missing,
    ))
    await db.commit()
    return {"reported": True, "file_missing": file_missing}


@router.get("/repository/download/{filename}")
async def repository_download(
    filename: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    _require_practitioner(auth)
    safe = Path(filename).name
    path = Path(settings.eval_docs_dir) / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    job = await db.scalar(
        select(EvalJob).where(EvalJob.result_file == str(path), EvalJob.status == "complete")
    )
    if not job:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    return FileResponse(
        str(path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=safe,
    )


@router.delete("/repository/{job_id}", status_code=204, response_model=None)
async def delete_repo_item(
    job_id: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> None:
    if not auth.has_role(RoleType.superuser, RoleType.lead_senior_practitioner):
        raise HTTPException(status_code=403, detail="Lead Senior Practitioner or superuser only.")
    job = await db.get(EvalJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.result_file:
        Path(job.result_file).unlink(missing_ok=True)
    await db.delete(job)
    await db.commit()
