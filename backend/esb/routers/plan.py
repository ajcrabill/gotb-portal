"""Strategic Plan Generator — ported natively from coach-devon's public /plan tool.

Originally ungated (public tool at gotbindex.com). Natively in the portal it is
gated: all practitioner roles, plus clients with an active district engagement
("paid clients"). Takes a desired outcome and optional clarifying answers, then:
1. Identifies missing SMART-Goal information (analyze endpoint)
2. Runs a lightweight research council — parallel web searches + multi-model
   brainstorming — to ground the plan in evidence and diverse ideation
3. Synthesizes a full draft strategic plan (generate endpoint)
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Any, AsyncGenerator

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.auth.rbac import AuthContext, get_auth_context
from esb.core.config import settings
from esb.core.database import get_db
from esb.models.billing import DistrictEngagement
from esb.models.user import RoleType

router = APIRouter(prefix="/api/plan", tags=["plan"])

_PRACTITIONER_ROLES = {
    RoleType.lead_senior_practitioner,
    RoleType.senior_practitioner,
    RoleType.practitioner_manager,
    RoleType.certified_practitioner,
    RoleType.practitioner_in_training,
    RoleType.superuser,
}

_FEEDBACK_FILE = Path(settings.plan_feedback_dir) / "plan_feedback.jsonl"
_FEEDBACK_FALLBACK = Path("/tmp/plan_feedback.jsonl")
_MAX_INJECTED_CORRECTIONS = 8

# ── Rate limiter (20 requests / person / hour) ─────────────────────────────────
_rate: dict[str, list[float]] = defaultdict(list)
_LIMIT, _WINDOW = 20, 3600


def _check_rate(key: str) -> None:
    now = time.time()
    hits = [t for t in _rate[key] if now - t < _WINDOW]
    if len(hits) >= _LIMIT:
        raise HTTPException(429, "Too many requests. Try again later.")
    hits.append(now)
    _rate[key] = hits


async def _require_plan_access(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    if auth.has_role(*_PRACTITIONER_ROLES):
        return auth
    if auth.has_role(RoleType.client):
        active = await db.scalar(
            select(DistrictEngagement).where(
                DistrictEngagement.person_id == auth.person_id,
                DistrictEngagement.ended_at.is_(None),
            )
        )
        if active:
            return auth
    raise HTTPException(status_code=403, detail="Strategic Plan Generator access required.")


# ── ESB framework context (shared by both prompts) ────────────────────────────
_ESB_CONTEXT = """\
You are an expert school board governance consultant trained in the Effective \
School Boards (ESB) framework from "Great On Their Behalf: Why School Boards \
Fail, How Yours Can Become Effective" by AJ Crabill.

CORE CONCEPTS:

SMART GOALS — must satisfy ALL of these:
• About STUDENT OUTCOMES: what students know or are able to do (NOT adult \
actions, programs, inputs, or even student outputs like attendance)
• Specific student population named (e.g., "3rd graders", "9th graders at \
risk of not graduating", "students receiving special education services")
• Specific measurement instrument named (e.g., "the district's MAP reading \
assessment", "the state summative literacy test", "the district's graduation rate")
• Starting point (W%) and ending point (Y%) — percentages or numbers
• Starting date AND ending date (both month AND year), typically 3–5 years apart

SMART GOAL FORMULA (use exactly):
"The percentage of [specific student population] who [student outcome] on \
[specific measurement] will [increase/decrease] from [W%] in [Month Year] to \
[Y%] by [Month Year]"

Example: "The percentage of 3rd graders reading on grade level on the \
district's summative literacy assessment will increase from 45% in \
September 2025 to 70% by September 2030."

GUARDRAILS — community values written as superintendent prohibitions:
• Format: "The superintendent will not [action that violates the community value]."
• Must be genuine prohibitions (avoid double negatives like "shall not fail to" \
or "shall not operate without" — those are hidden directives)
• Example: "The superintendent will not make major decisions without first \
engaging impacted students, families, community members, and staff."
• Typically 1–3 guardrails

INTERIM GOALS — student OUTPUT metrics predictive of the Goal:
• Knowable DURING the cycle (benchmarks, interim assessments, on-track indicators)
• NOT the same as the Goal metric — must be a different, leading indicator
• 1–3 year timeframe
• Same SMART formula as Goals
• Select 2–3 per Goal

INTERIM GUARDRAILS — output metrics predictive of honoring the Guardrail:
• Same SMART formula
• 1–3 year timeframe
• Select 1–2 per Guardrail

INITIATIVES — adult INPUT commitments:
• Initiatives describe what ADULTS will DO or COMMIT TO — not student actions \
or results of adult work
• Format: "By [Month Year], [adult role] will have [specific adult action with \
measurable evidence it was completed]."
• CORRECT examples:
  "By August [Year], the superintendent will have ensured that 100% of K-3 \
classroom teachers completed 40 hours of structured literacy coaching."
  "By [Month Year], the district will have adopted a Tier 1 phonics curriculum \
for grades K-3 and provided all teachers with at least 20 hours of \
implementation training."
• WRONG (output-style — describes a result, not an adult input):
  "Reading scores will improve 10% by Year 2."
  "Students will receive 30 minutes of daily intervention."
• WRONG (not SMART — no measurement, no deadline, no specific action):
  "Teachers will provide data-driven instruction."
  "The district will support professional development."
• Must name an adult actor (superintendent, principal, director, board)
• Must be measurable: a verifiable yes/no — did the adult do it or not?
• Must be time-bound with a specific deadline
• Uses school system resources (time, talent, or money)
• Select EXACTLY 3 per Interim Goal or Interim Guardrail

KEY DISTINCTIONS:
• Student OUTCOMES (Goals): summative assessment scores, graduation rates, \
AP pass rates, college persistence — knowable at END of year
• Student OUTPUTS (Interim Goals): interim assessments, on-track indicators, \
benchmark results — knowable DURING the year
• Adult INPUTS (Initiatives): staffing, programs, curriculum, training — \
knowable at START of year; describe adult commitments, not student results
"""

_ANALYZE_SYSTEM = _ESB_CONTEXT + """
YOUR TASK: Review the user's desired outcome and identify exactly which \
information is MISSING to build a valid SMART Goal and strategic plan.

Check for these SMART Goal elements — if clearly present or strongly \
inferable, do NOT ask. Only ask when truly missing:
  "population"       — specific student group
  "instrument"       — specific measurement/assessment
  "baseline"         — starting percentage or number
  "baseline_date"    — starting month and year
  "target"           — ending percentage or number
  "target_date"      — ending month and year (3–5 years out)

ALWAYS ask about community values (for Guardrails):
  "community_values" — 1–3 non-negotiables that must be honored

If the input already specifies something fully, skip that question. Ask at \
most 7 questions total. Keep questions brief and practitioner-friendly.

Return ONLY valid JSON — no markdown, no prose:
{"questions": [{"id": "population", "question": "Which specific group..."}, ...]}

If the outcome is already a complete SMART Goal (has all 6 elements), only \
ask the community_values question.
"""

_SKELETON_SYSTEM = _ESB_CONTEXT + """
YOUR TASK: Generate the STRUCTURE of a strategic plan — Goals, Guardrails, \
Interim Goals, and Interim Guardrails. Do NOT generate any Initiatives yet.

This is a PRACTITIONER DRAFT. Use plausible illustrative numbers in brackets \
where real data is missing, e.g., "[45%]". Never leave a percentage blank.

REQUIRED QUANTITIES:
• EXACTLY 3 Guardrails
• EXACTLY 3 Interim Goals nested inside smart_goal
• EXACTLY 3 Interim Guardrails nested inside each Guardrail

Return ONLY valid JSON — no markdown, no code fences:
{
  "smart_goal": {
    "title": "3–5 word short title",
    "statement": "Full SMART goal statement following the formula exactly",
    "interim_goals": [
      {"title": "Short title", "statement": "Full SMART interim goal statement"},
      {"title": "Short title", "statement": "Full SMART interim goal statement"},
      {"title": "Short title", "statement": "Full SMART interim goal statement"}
    ]
  },
  "guardrails": [
    {
      "title": "3–5 word short title",
      "statement": "The superintendent will not...",
      "interim_guardrails": [
        {"title": "Short title", "statement": "Full SMART interim guardrail statement"},
        {"title": "Short title", "statement": "Full SMART interim guardrail statement"},
        {"title": "Short title", "statement": "Full SMART interim guardrail statement"}
      ]
    }
  ]
}
"""

_SYNTHESIS_SYSTEM = _ESB_CONTEXT + """
YOUR TASK: You have a strategic plan skeleton and peer-reviewed research for \
each interim goal and guardrail. Add EXACTLY 3 Initiatives to every interim item.

INITIATIVE QUALITY CHECK — apply before writing EACH initiative:
  1. Is the subject an adult actor (superintendent, principal, director, board)?
  2. Does it describe what the adult will DO/COMMIT — not what will result?
  3. Is it SMART: specific action, measurable (did it happen?), time-bound?

CITATION RULES — non-negotiable:
  • Each initiative MUST cite the 1–5 most relevant studies from the research \
provided for its interim item — include more when multiple studies directly \
support the initiative, fewer when only one is a strong fit
  • ONLY use URLs that appear in the "SOURCE URLS" list for that interim item
  • Copy each URL character-for-character — NEVER modify, shorten, or invent a URL
  • If a URL is a DOI (https://doi.org/…), format the text as: \
"Author et al. (Year). Title. Journal."
  • If no DOI is available for a URL, use the provided URL as-is
  • NEVER fabricate a citation or DOI — use only what was provided

Return ONLY valid JSON — no markdown, no code fences:
{
  "smart_goal": {
    "title": "...",
    "statement": "...",
    "interim_goals": [
      {
        "title": "...",
        "statement": "...",
        "initiatives": [
          {
            "title": "Short initiative name",
            "statement": "By [Month Year], [adult role] will have [specific adult action verifiable as complete].",
            "description": "1–2 sentences on what this commitment involves and why it drives the interim goal.",
            "citations": [
              {"url": "exact URL from research list", "text": "Full citation text"}
            ]
          }
        ]
      }
    ]
  },
  "guardrails": [
    {
      "title": "...",
      "statement": "...",
      "interim_guardrails": [
        {
          "title": "...",
          "statement": "...",
          "initiatives": [
            {
              "title": "Short initiative name",
              "statement": "By [Month Year], [adult role] will have [specific adult action verifiable as complete].",
              "description": "1–2 sentences on what this commitment involves and why it protects the guardrail.",
              "citations": [
                {"url": "exact URL from research list", "text": "Full citation text"}
              ]
            }
          ]
        }
      ]
    }
  ]
}
"""


# ── LLM helpers ───────────────────────────────────────────────────────────────

def _extract_content(data: dict) -> str:
    """Handle thinking models that put output in 'reasoning' when content is null."""
    msg = data.get("choices", [{}])[0].get("message", {})
    return msg.get("content", "") or msg.get("reasoning", "") or ""


async def _llm_json(system: str, user: str, client: httpx.AsyncClient | None = None) -> dict:
    """Call the configured LLM and return parsed JSON."""
    if not settings.openrouter_api_key:
        raise HTTPException(503, "LLM service not configured.")

    async def _call(c: httpx.AsyncClient) -> dict:
        resp = await c.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.llm_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            },
        )
        if resp.status_code != 200:
            raise HTTPException(502, f"LLM error: {resp.status_code} — {resp.text[:200]}")
        content = _extract_content(resp.json())
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise HTTPException(502, "LLM returned invalid JSON. Please try again.") from exc

    if client:
        return await _call(client)
    async with httpx.AsyncClient(timeout=90.0) as c:
        return await _call(c)


async def _web_search(client: httpx.AsyncClient, query: str) -> str:
    """Single Perplexity web search. Returns text or empty string on failure."""
    try:
        resp = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "perplexity/sonar",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a K-12 education research assistant. "
                            "Be concise. Cite specific programs, studies, percentages, "
                            "and districts when possible."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                "max_tokens": 900,
            },
        )
        if resp.status_code != 200:
            return ""
        return _extract_content(resp.json())
    except Exception:
        return ""


async def _brainstorm(
    client: httpx.AsyncClient,
    model: str,
    advisory_role: str,
    brief: str,
) -> str:
    """Single ideation call. Returns text or empty string on failure.

    Falls back to the same model without :free suffix on 429.
    """
    async def _attempt(m: str) -> str:
        try:
            resp = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": m,
                    "messages": [
                        {"role": "system", "content": advisory_role},
                        {"role": "user", "content": brief},
                    ],
                    "max_tokens": 1800,
                    "temperature": 0.6,
                },
            )
            if resp.status_code == 429 and m.endswith(":free"):
                return await _attempt(m[: -len(":free")])
            if resp.status_code != 200:
                return ""
            return _extract_content(resp.json())
        except Exception:
            return ""

    return await _attempt(model)


async def _gather_research_and_ideation(
    outcome: str,
    answers: dict[str, str],
) -> str:
    """Run web research + multi-model brainstorming in parallel.

    Returns a combined context block to inject into the synthesis prompt.
    Falls back gracefully if any calls fail — plan generation proceeds
    with whatever context is available.
    """
    population = answers.get("population", "students")
    community_values = answers.get("community_values", "equitable access and community engagement")
    outcome_short = outcome[:120]

    search_q1 = (
        f"What evidence-based interventions most effectively improve "
        f"{outcome_short} outcomes for {population} in US K-12 schools? "
        f"Include specific programs, measured results, and citations."
    )
    search_q2 = (
        f"What leading-indicator metrics do high-performing US school districts "
        f"use to track progress toward {outcome_short}? "
        f"What interim assessments or early-warning indicators are most predictive?"
    )

    brainstorm_brief = (
        f"Student outcome goal area: {outcome_short}\n"
        f"Target population: {population}\n"
        f"Community values to protect: {community_values}\n\n"
        f"Based on your expertise, brainstorm 4–6 concrete, specific options for "
        f"each of the following. Be specific — name real programs, assessments, and "
        f"policy approaches where possible:\n"
        f"1. SMART Goal statement candidates (follow this exact formula: "
        f"'The percentage of [population] who [outcome] on [assessment] will "
        f"[increase/decrease] from [W%] in [Month Year] to [Y%] by [Month Year]')\n"
        f"2. Guardrail candidates (superintendent prohibition statements protecting "
        f"the stated community values)\n"
        f"3. Interim Goal candidates (student output metrics predictive of the goal, "
        f"measurable multiple times per year)\n"
        f"4. Initiative candidates (evidence-based strategies with clear owners and "
        f"resource requirements)\n"
        f"Label each section clearly. Be concrete and specific."
    )

    role_research = (
        "You are an expert in K-12 student outcome measurement, education research, "
        "and evidence-based intervention design. You specialize in identifying what "
        "actually moves student achievement metrics in public school systems, and in "
        "selecting leading indicators that reliably predict summative outcomes."
    )
    role_governance = (
        "You are an expert in school board governance, community engagement, and "
        "educational equity policy. You specialize in crafting guardrails that protect "
        "community values, designing initiatives that build community trust, and "
        "identifying the systemic adult-behavior changes most likely to drive student "
        "outcome improvements."
    )

    async with httpx.AsyncClient(timeout=45.0) as client:
        results = await asyncio.gather(
            _web_search(client, search_q1),
            _web_search(client, search_q2),
            _brainstorm(client, "openrouter/auto", role_research, brainstorm_brief),
            _brainstorm(client, "z-ai/glm-4.5-air:free", role_governance, brainstorm_brief),
            return_exceptions=True,
        )

    search1, search2, ideas_research, ideas_governance = [
        r if isinstance(r, str) else "" for r in results
    ]

    sections = []
    if search1:
        sections.append(f"## Web Research: Evidence-Based Interventions\n{search1}")
    if search2:
        sections.append(f"## Web Research: Leading Indicator Metrics\n{search2}")
    if ideas_research:
        sections.append(f"## Brainstorm — Research & Measurement Expert\n{ideas_research}")
    if ideas_governance:
        sections.append(f"## Brainstorm — Governance & Equity Expert\n{ideas_governance}")

    return "\n\n".join(sections)


async def _research_interim(
    client: httpx.AsyncClient,
    label: str,
    statement: str,
) -> dict:
    """One Perplexity/Sonar call for peer-reviewed research on an interim item.

    Returns {"label", "content", "urls"} where urls are the verified source
    URLs returned by the Perplexity API (never hallucinated by us).
    """
    query = (
        f"Find peer-reviewed research studies on specific actions that K-12 "
        f"educators, school administrators, or school districts can take related to: "
        f"{statement[:200]}\n\n"
        f"For each study, provide the full citation: authors, year, article title, "
        f"journal name, and DOI link formatted as https://doi.org/... "
        f"Only include studies with verifiable DOI links. List 4–6 studies."
    )
    try:
        resp = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "perplexity/sonar",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are an academic education research librarian. "
                            "Only cite real studies with verifiable DOI links. "
                            "Never fabricate a DOI. If you cannot verify a study's "
                            "DOI, omit that citation entirely. "
                            "Format DOIs as https://doi.org/..."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                "max_tokens": 1200,
            },
        )
        if resp.status_code != 200:
            return {"label": label, "content": "", "urls": []}
        data = resp.json()
        content = _extract_content(data)
        urls: list[str] = data.get("citations", [])
        return {"label": label, "content": content, "urls": urls}
    except Exception:
        return {"label": label, "content": "", "urls": []}


async def _research_all_interims(skeleton: dict, population: str) -> list[dict]:
    """Fire one Perplexity call per interim goal and per interim guardrail in parallel.

    Returns a list of research dicts in the same order as the skeleton's items.
    """
    items: list[dict] = []

    ig_list = (skeleton.get("smart_goal") or {}).get("interim_goals", [])
    for i, ig in enumerate(ig_list):
        items.append({
            "label": f"Interim Goal 1.{i + 1}: {ig.get('title', '')}",
            "statement": ig.get("statement", ""),
        })

    for gi, gr in enumerate(skeleton.get("guardrails", []), 1):
        for j, igr in enumerate(gr.get("interim_guardrails", []), 1):
            items.append({
                "label": f"Interim Guardrail {gi}.{j}: {igr.get('title', '')}",
                "statement": igr.get("statement", ""),
            })

    if not items:
        return []

    async with httpx.AsyncClient(timeout=45.0) as client:
        results = await asyncio.gather(
            *[_research_interim(client, it["label"], it["statement"]) for it in items],
            return_exceptions=True,
        )

    return [
        r if isinstance(r, dict) else {"label": items[i]["label"], "content": "", "urls": []}
        for i, r in enumerate(results)
    ]


def _build_synthesis_user_msg(
    skeleton: dict,
    outcome: str,
    answers_block: str,
    research_ctx: str,
    interim_research: list[dict],
) -> str:
    """Assemble the large synthesis prompt from skeleton + all research sources."""
    research_blocks = []
    for r in interim_research:
        urls_str = "\n".join(f"  - {u}" for u in r.get("urls", [])) or "  (none verified)"
        block = (
            f"### Research for {r['label']}\n"
            f"{r.get('content', '') or '(no content returned)'}\n\n"
            f"SOURCE URLS (copy exactly — never modify):\n{urls_str}"
        )
        research_blocks.append(block)

    skeleton_json = json.dumps(skeleton, indent=2)
    research_section = "\n\n".join(research_blocks) if research_blocks else "(no citation data)"

    council_note = (
        "\n\n[General research council output for additional context — "
        "do NOT use as citation source; use only the per-interim SOURCE URLS above]\n"
        + research_ctx
    ) if research_ctx else ""

    corrections = _load_recent_corrections()
    corrections_block = f"\n\n{corrections}" if corrections else ""

    return (
        f'Desired outcome: "{outcome}"{answers_block}{council_note}{corrections_block}\n\n'
        f"Strategic plan skeleton:\n{skeleton_json}\n\n"
        f"Peer-reviewed research per interim item:\n{research_section}\n\n"
        "Now add EXACTLY 3 initiatives per interim item, each citing 1–2 real studies "
        "from its SOURCE URLS. Follow all citation and initiative rules. Return JSON only."
    )


# ── Request/response models ───────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    outcome: str


class GenerateRequest(BaseModel):
    outcome: str
    answers: dict[str, str] = {}


class PlanAnnotation(BaseModel):
    element_id: str
    element_type: str = ""
    title: str = ""
    statement: str = ""
    rating: str          # "good" | "flag"
    rewrite: str = ""
    note: str = ""


class PlanFeedbackRequest(BaseModel):
    plan_id: str
    outcome: str = ""
    annotations: list[PlanAnnotation] = []


# ── Feedback storage ────────────────────────────────────────────────────────────

def _feedback_path() -> Path:
    try:
        _FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        return _FEEDBACK_FILE
    except OSError:
        return _FEEDBACK_FALLBACK


def _append_feedback(payload: PlanFeedbackRequest, person_id: str) -> None:
    path = _feedback_path()
    record = {
        "ts": time.time(),
        "person_id": person_id,
        "plan_id": payload.plan_id,
        "outcome": payload.outcome,
        "annotations": [a.model_dump() for a in payload.annotations],
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _load_recent_corrections(n: int = _MAX_INJECTED_CORRECTIONS) -> str:
    """Return a formatted block of the most recent expert corrections.

    Only 'flag' ratings with a non-empty rewrite are included — those
    are the actionable signals worth injecting into the synthesis prompt.
    """
    path = _feedback_path()
    if not path.exists():
        return ""

    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return ""

    corrections: list[str] = []
    for line in reversed(lines):
        if len(corrections) >= n:
            break
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        for ann in record.get("annotations", []):
            if ann.get("rating") == "flag" and ann.get("rewrite", "").strip():
                label = ann.get("element_type", "element").replace("_", " ").title()
                corrections.append(
                    f'• [{label}] Original: "{ann.get("statement", "")[:120]}"\n'
                    f'  Expert correction: "{ann["rewrite"].strip()}"\n'
                    + (f'  Note: "{ann["note"].strip()}"\n' if ann.get("note", "").strip() else "")
                )
            if len(corrections) >= n:
                break

    if not corrections:
        return ""

    return (
        "PRIOR EXPERT CORRECTIONS — study carefully and do not repeat these mistakes:\n"
        + "".join(corrections)
    )


# ── Endpoints ───────────────────────────────────────────────────────────────────
@router.post("/analyze")
async def analyze_outcome(
    payload: AnalyzeRequest,
    auth: Annotated[AuthContext, Depends(_require_plan_access)],
) -> dict[str, Any]:
    """Return clarifying questions needed to turn the outcome into a SMART Goal."""
    _check_rate(str(auth.person_id))

    outcome = payload.outcome.strip()
    if not outcome:
        raise HTTPException(400, "Outcome text is required.")
    if len(outcome) > 2000:
        raise HTTPException(400, "Outcome too long (max 2,000 characters).")

    user_msg = (
        f'The practitioner has entered this desired outcome:\n\n"{outcome}"\n\n'
        "What clarifying questions, if any, are needed to build a SMART Goal "
        "and strategic plan? Return JSON."
    )
    result = await _llm_json(_ANALYZE_SYSTEM, user_msg)
    return {"questions": result.get("questions", [])}


@router.post("/feedback")
async def save_feedback(
    payload: PlanFeedbackRequest,
    auth: Annotated[AuthContext, Depends(_require_plan_access)],
) -> dict[str, Any]:
    """Store expert annotations on a generated plan.

    Flagged items with rewrites are injected into future synthesis prompts
    as few-shot corrections so the model learns from AJ's edits.
    """
    _check_rate(str(auth.person_id))

    if not payload.annotations:
        raise HTTPException(400, "No annotations provided.")

    try:
        _append_feedback(payload, str(auth.person_id))
    except Exception as exc:
        raise HTTPException(500, f"Failed to save feedback: {exc}") from exc

    flagged = sum(1 for a in payload.annotations if a.rating == "flag")
    good    = sum(1 for a in payload.annotations if a.rating == "good")
    return {"ok": True, "saved": len(payload.annotations), "flagged": flagged, "good": good}


@router.post("/generate")
async def generate_plan(
    payload: GenerateRequest,
    auth: Annotated[AuthContext, Depends(_require_plan_access)],
) -> StreamingResponse:
    """Generate a citation-grounded strategic plan via a 4-phase pipeline.

    Returns a Server-Sent Events stream so the browser connection stays alive
    through slow/idle-connection timeouts. Each phase yields a progress
    event; keepalive comment lines are sent every 4 s while waiting.

    Phase A ‖ Phase B (parallel):
      A — general research council (web searches + multi-model ideation)
      B — generate plan skeleton (goal + guardrails + interim items, no initiatives)
    Phase C — one Perplexity/Sonar call per interim goal and interim guardrail
              in parallel; each call returns real peer-reviewed citations
    Phase D — synthesis: fill every interim item with 3 SMART adult-input
              initiatives, each citing only verified DOIs from Phase C
    """
    _check_rate(str(auth.person_id))

    outcome = payload.outcome.strip()
    if not outcome:
        raise HTTPException(400, "Outcome text is required.")

    population = payload.answers.get("population", "students")
    answers_block = ""
    if payload.answers:
        answers_block = "\n\nClarifying answers from the practitioner:\n" + "\n".join(
            f"  • {qid}: {ans}" for qid, ans in payload.answers.items() if ans.strip()
        )

    skeleton_msg = (
        f'Desired outcome: "{outcome}"{answers_block}\n\n'
        "Generate the plan skeleton — goals, guardrails, interim goals, "
        "interim guardrails only. No initiatives yet. Return JSON only."
    )

    async def event_stream() -> AsyncGenerator[str, None]:
        yield 'data: {"phase":"started"}\n\n'

        r_task = asyncio.create_task(_gather_research_and_ideation(outcome, payload.answers))
        s_task = asyncio.create_task(_llm_json(_SKELETON_SYSTEM, skeleton_msg))
        pending: set = {r_task, s_task}
        while pending:
            _, pending = await asyncio.wait(pending, timeout=4.0)
            if pending:
                yield ": keepalive\n\n"

        try:
            research_ctx: str = r_task.result()
        except Exception:
            research_ctx = ""
        try:
            skeleton: dict = s_task.result()
        except Exception:
            yield f'data: {json.dumps({"error": "Failed to generate plan structure. Please try again."})}\n\n'
            return

        yield 'data: {"phase":"skeleton"}\n\n'

        c_task = asyncio.create_task(_research_all_interims(skeleton, population))
        pending = {c_task}
        while pending:
            _, pending = await asyncio.wait(pending, timeout=4.0)
            if pending:
                yield ": keepalive\n\n"

        try:
            interim_research: list = c_task.result()
        except Exception:
            interim_research = []

        yield 'data: {"phase":"research"}\n\n'

        synthesis_msg = _build_synthesis_user_msg(
            skeleton, outcome, answers_block, research_ctx, interim_research
        )
        d_task = asyncio.create_task(_llm_json(_SYNTHESIS_SYSTEM, synthesis_msg))
        pending = {d_task}
        while pending:
            _, pending = await asyncio.wait(pending, timeout=4.0)
            if pending:
                yield ": keepalive\n\n"

        try:
            plan: dict = d_task.result()
        except Exception:
            yield f'data: {json.dumps({"error": "Plan synthesis failed. Please try again."})}\n\n'
            return

        yield f'data: {json.dumps({"done": True, "plan": plan})}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
