"""Background job processor for Time Use Evaluations.

Ported from esby-portal's app/worker.py. Runs as an in-process asyncio
task (matches the source's model — no separate queue/worker process).
"""
import datetime
import traceback
from pathlib import Path
from uuid import UUID

import structlog

from esb.core.config import settings
from esb.core.database import AsyncSessionLocal
from esb.eval.analyzer import (
    GOVERNANCE_CRITERIA,
    aggregate_multi_meeting_scores,
    classify_agenda_items,
    compute_category_totals,
    extract_agenda_items,
    find_district_meetings,
    generate_coaching_reflections,
    generate_multi_meeting_reflections,
    score_meeting_governance,
)
from esb.eval.detector import detect_platform
from esb.eval.docx_gen import generate_evaluation_docx, generate_multi_meeting_docx
from esb.eval.extractor import extract_transcript
from esb.models.eval import EvalJob
from esb.models.user import Person

log = structlog.get_logger()

SPAN_MONTHS = {"1_meeting": 0, "1_month": 1, "3_month": 3, "6_month": 6}
SPAN_MAX_MEETINGS = {"1_meeting": 1, "1_month": 4, "3_month": 8, "6_month": 12}
SPAN_LABELS = {
    "1_meeting": "Single Meeting",
    "1_month": "1-Month Review",
    "3_month": "3-Month Review",
    "6_month": "6-Month Review",
}


def _docs_path() -> Path:
    p = Path(settings.eval_docs_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


async def _update_job(job_id: UUID, **kwargs) -> None:
    kwargs["updated_at"] = datetime.datetime.now(datetime.timezone.utc)
    async with AsyncSessionLocal() as db:
        job = await db.get(EvalJob, job_id)
        if not job:
            return
        for k, v in kwargs.items():
            setattr(job, k, v)
        await db.commit()


async def process_job(job_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        job = await db.get(EvalJob, job_id)
        if not job:
            return
        person = await db.get(Person, job.person_id)
        review_span = job.review_span or "1_meeting"
        video_url = job.video_url
        district = job.district_name or "Unknown District"
        meeting_date = job.meeting_date or "Unknown Date"
        meeting_type = job.meeting_type or "Regular Board Meeting"

    await _update_job(job_id, status="processing")

    if review_span == "1_meeting":
        await _process_single_meeting(job_id, video_url, district, meeting_date, meeting_type, person)
    else:
        await _process_multi_meeting(job_id, video_url, district, meeting_date, meeting_type, person, review_span)


async def _process_single_meeting(job_id, video_url, district, meeting_date, meeting_type, person) -> None:
    try:
        platform = detect_platform(video_url)
        await _update_job(job_id, platform=platform)

        transcript = await extract_transcript(video_url, str(job_id))
        agenda_items = await extract_agenda_items(transcript, district, meeting_date)
        classified = await classify_agenda_items(agenda_items)
        total_minutes = sum(i.get("minutes", 0) for i in classified)
        category_totals = compute_category_totals(classified, total_minutes)
        coaching = await generate_coaching_reflections(
            agenda_items, classified, district, total_minutes,
            category_totals["goal_focused_minutes"],
        )

        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in district)
        doc_filename = f"{safe_name}_{meeting_date}_{str(job_id)[:8]}.docx"
        doc_path = _docs_path() / doc_filename
        generate_evaluation_docx(
            output_path=str(doc_path),
            district=district,
            meeting_date=meeting_date,
            meeting_type=meeting_type,
            video_url=video_url,
            agenda_link="",
            strategic_plan_link="",
            agenda_items=agenda_items,
            classified_items=classified,
            category_totals=category_totals,
            coaching=coaching,
        )

        result_url = f"{settings.backend_url}/api/eval/repository/download/{doc_filename}"
        await _update_job(job_id, status="complete", result_file=str(doc_path), result_url=result_url)

    except Exception as e:
        tb = traceback.format_exc()
        log.error("eval.job_failed", job_id=str(job_id), error=str(e))
        await _update_job(job_id, status="error", error_msg=f"{e}\n{tb[:1000]}")


async def _process_multi_meeting(job_id, video_url, district, anchor_date, meeting_type, person, review_span) -> None:
    try:
        months = SPAN_MONTHS[review_span]
        max_meetings = SPAN_MAX_MEETINGS[review_span]
        span_label = SPAN_LABELS[review_span]

        await _update_job(job_id, status="processing", error_msg=f"Finding {span_label} meetings for {district}…")
        meetings = await find_district_meetings(district, video_url, months, max_meetings, anchor_date=anchor_date)

        submitted_urls = {m["url"] for m in meetings}
        if video_url not in submitted_urls:
            meetings.insert(0, {
                "url": video_url,
                "date": anchor_date or datetime.date.today().isoformat(),
                "title": meeting_type,
            })
        meetings = meetings[:max_meetings]

        scored_meetings = []
        for i, meeting in enumerate(meetings):
            url = meeting["url"]
            date = meeting.get("date", "Unknown")
            await _update_job(job_id, error_msg=f"Transcribing meeting {i+1} of {len(meetings)} ({date})…")
            try:
                transcript = await extract_transcript(url, f"{job_id}_m{i}")
                score = await score_meeting_governance(transcript, district, date)
                score["url"] = url
                scored_meetings.append(score)
            except Exception as e:
                scored_meetings.append({
                    "meeting_date": date,
                    "url": url,
                    "error": str(e),
                    "composite": 0,
                    **{c["key"]: {"score": 0, "notes": "Could not transcribe", "examples": ""} for c in GOVERNANCE_CRITERIA},
                })

        if not scored_meetings:
            raise RuntimeError("Could not transcribe any meetings in the selected period.")

        aggregate = aggregate_multi_meeting_scores(scored_meetings)
        coaching = await generate_multi_meeting_reflections(scored_meetings, aggregate, district, span_label)

        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in district)
        doc_filename = f"{safe_name}_{review_span}_{str(job_id)[:8]}.docx"
        doc_path = _docs_path() / doc_filename
        generate_multi_meeting_docx(
            output_path=str(doc_path),
            district=district,
            span_label=span_label,
            scored_meetings=scored_meetings,
            aggregate=aggregate,
            coaching=coaching,
        )

        result_url = f"{settings.backend_url}/api/eval/repository/download/{doc_filename}"
        await _update_job(
            job_id, status="complete", result_file=str(doc_path), result_url=result_url,
            meetings_analyzed=len(scored_meetings), error_msg=None,
        )

    except Exception as e:
        tb = traceback.format_exc()
        log.error("eval.multi_job_failed", job_id=str(job_id), error=str(e))
        await _update_job(job_id, status="error", error_msg=f"{e}\n{tb[:1000]}")
