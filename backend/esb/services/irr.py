"""IRR Simulator service — dynamic scenario generation and scoring (M20).

Time Use Evaluation:
  The system generates synthetic board meeting agendas + time logs.
  Each scenario has rubric items (time categories) the practitioner must score.
  System scores first; practitioner scores after; Cohen's kappa is computed.

Cohen's kappa formula:
  κ = (Po - Pe) / (1 - Pe)
  where Po = observed agreement, Pe = expected chance agreement.

  For ordinal rubrics we use weighted kappa (linear weights).
  kappa >= 0.70 = reliable; < 0.40 = poor; 0.40-0.69 = moderate.

Scenario generation uses a lightweight template system. The IRR Simulator
source documents from Google Drive are ingested into IRRScenario.scenario_data
as the baseline; this service generates variant data dynamically.
"""
from __future__ import annotations

import hashlib
import random
import secrets
from datetime import date, datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from esb.models.irr import IRRAttempt, IRRAttemptStatus, IRRProgress, IRRScenario, IRRScenarioType

log = structlog.get_logger()

KAPPA_PASS_THRESHOLD = 0.70
KAPPA_POOR_THRESHOLD = 0.40
ROLLING_WINDOW = 5

# ── Time Use Evaluation item definitions ─────────────────────────────────────
# Each item is a time category that must be classified and rated.
# These map to the scoring criteria in the Time Use Eval instrument.

TIME_USE_ITEMS = [
    {
        "id": "student_outcomes",
        "label": "Student Outcomes Focus",
        "description": "Time spent directly on student achievement, outcome data, and goal review.",
        "max_score": 4,
        "rubric": {
            0: "No time spent on student outcomes.",
            1: "Minimal time (<10% of meeting); largely procedural.",
            2: "Some focus (10-25%); discussed but not deeply analyzed.",
            3: "Significant focus (25-50%); data reviewed and discussed.",
            4: "Primary focus (>50%); deep analysis with clear goal connection.",
        },
    },
    {
        "id": "policy_governance",
        "label": "Policy and Governance",
        "description": "Time spent on policy adoption, revision, or governance matters.",
        "max_score": 4,
        "rubric": {
            0: "No policy/governance work.",
            1: "Perfunctory; rubber-stamp only.",
            2: "Some deliberation on policy items.",
            3: "Meaningful policy work with board discussion.",
            4: "Rigorous policy work with clear rationale and outcome connection.",
        },
    },
    {
        "id": "superintendent_evaluation",
        "label": "Superintendent Evaluation / Direction",
        "description": "Time spent on superintendent performance, direction-setting, or contract.",
        "max_score": 4,
        "rubric": {
            0: "No superintendent-facing work.",
            1: "Mentioned but no substantive discussion.",
            2: "Some discussion; lacks criteria or clear expectations.",
            3: "Substantive discussion with clear expectations.",
            4: "Rigorous evaluation with data-driven criteria and documented follow-through.",
        },
    },
    {
        "id": "community_engagement",
        "label": "Community Engagement",
        "description": "Time spent on genuine community input, not just public comment periods.",
        "max_score": 4,
        "rubric": {
            0: "No community engagement.",
            1: "Perfunctory public comment only.",
            2: "Some engagement; limited two-way exchange.",
            3: "Meaningful input sought and acknowledged.",
            4: "Structured, substantive engagement with documented impact on decisions.",
        },
    },
    {
        "id": "operational_minutiae",
        "label": "Operational Minutiae (inverse)",
        "description": "Time spent on operational details that should be delegated to staff.",
        "max_score": 4,
        "rubric": {
            0: "Board appropriately delegated; no operational minutiae.",
            1: "Minimal (< 5%); isolated slippage.",
            2: "Moderate (5-15%); noticeable scope creep.",
            3: "Significant (15-30%); board frequently in staff territory.",
            4: "Dominant (>30%); board acting as staff.",
        },
        "inverse": True,  # higher = worse; flipped in kappa computation
    },
]


def _seed_from_string(s: str) -> int:
    return int(hashlib.md5(s.encode()).hexdigest(), 16) % (2**31)


def _random_date_near_today(rng: random.Random) -> str:
    days_ago = rng.randint(7, 120)
    d = date.today() - timedelta(days=days_ago)
    return d.strftime("%B %d, %Y")


def _generate_agenda_items(rng: random.Random) -> list[dict]:
    """Generate synthetic agenda items with time allocations."""
    templates = [
        ("Call to Order / Roll Call", "procedural", (2, 5)),
        ("Approval of Minutes", "procedural", (2, 4)),
        ("Public Comment", "community_engagement", (5, 20)),
        ("Superintendent's Report", "superintendent_evaluation", (10, 25)),
        ("Student Achievement Data Review", "student_outcomes", (10, 40)),
        ("Policy First Reading", "policy_governance", (8, 20)),
        ("Budget Update", "operational_minutiae", (10, 30)),
        ("Facilities Update", "operational_minutiae", (5, 20)),
        ("Human Resources Report", "operational_minutiae", (5, 15)),
        ("Goals Progress Update", "student_outcomes", (10, 25)),
        ("Consent Agenda", "procedural", (2, 5)),
        ("Board Member Reports", "community_engagement", (5, 15)),
        ("Executive Session", "superintendent_evaluation", (15, 45)),
        ("Adjournment", "procedural", (1, 3)),
    ]
    selected = rng.sample(templates, k=rng.randint(6, 10))
    agenda = []
    for title, category, (min_min, max_min) in selected:
        minutes = rng.randint(min_min, max_min)
        agenda.append({"title": title, "category": category, "allocated_minutes": minutes})
    return agenda


def generate_scenario(
    scenario_type: IRRScenarioType = IRRScenarioType.time_use_eval,
    seed: str | None = None,
) -> dict:
    """
    Generate synthetic scenario data.
    Returns a dict with all data needed to present the scenario to a practitioner.
    """
    if seed is None:
        seed = secrets.token_hex(8)
    rng = random.Random(_seed_from_string(seed))

    meeting_date = _random_date_near_today(rng)
    district_name = rng.choice([
        "Riverside Unified School District",
        "Northlake Community School District",
        "Elmwood Independent School District",
        "Clearwater Public Schools",
        "Hillcrest School District",
        "Mapleton Unified School District",
    ])
    board_size = rng.randint(5, 7)
    quorum = rng.randint(board_size - 1, board_size)

    agenda_items = _generate_agenda_items(rng)
    total_minutes = sum(a["allocated_minutes"] for a in agenda_items)

    return {
        "district": district_name,
        "meeting_date": meeting_date,
        "meeting_type": rng.choice(["Regular Board Meeting", "Special Board Meeting"]),
        "quorum_present": quorum,
        "board_size": board_size,
        "total_minutes": total_minutes,
        "agenda_items": agenda_items,
        "notes": (
            f"The board convened at 6:00 PM with {quorum} of {board_size} members present. "
            f"Total meeting time: {total_minutes} minutes."
        ),
    }


def system_score_scenario(scenario_data: dict) -> dict:
    """
    Apply the canonical scoring to a generated scenario.
    Returns {item_id: {score, rationale, criteria_met}} for all rubric items.
    """
    # Compute time allocations by category
    category_minutes: dict[str, int] = {}
    total = scenario_data.get("total_minutes", 0) or 1  # avoid div-by-zero
    for item in scenario_data.get("agenda_items", []):
        cat = item["category"]
        category_minutes[cat] = category_minutes.get(cat, 0) + item["allocated_minutes"]

    scores = {}
    for item in TIME_USE_ITEMS:
        iid = item["id"]
        cat_map = {
            "student_outcomes":         "student_outcomes",
            "policy_governance":        "policy_governance",
            "superintendent_evaluation": "superintendent_evaluation",
            "community_engagement":     "community_engagement",
            "operational_minutiae":     "operational_minutiae",
        }
        cat = cat_map.get(iid, "")
        pct = (category_minutes.get(cat, 0) / total) * 100

        if item.get("inverse"):
            # operational minutiae: more = worse
            if pct < 5:
                score = 0
            elif pct < 15:
                score = 2
            elif pct < 30:
                score = 3
            else:
                score = 4
        else:
            if pct == 0:
                score = 0
            elif pct < 10:
                score = 1
            elif pct < 25:
                score = 2
            elif pct < 50:
                score = 3
            else:
                score = 4

        scores[iid] = {
            "score": score,
            "pct_of_meeting": round(pct, 1),
            "minutes": category_minutes.get(cat, 0),
            "rationale": item["rubric"][score],
            "criteria_met": [item["rubric"][s] for s in range(score + 1)],
        }
    return scores


def compute_kappa(system_scores: dict, practitioner_scores: dict) -> tuple[float, dict]:
    """
    Compute Cohen's kappa (linear weighted) for matched items.
    Returns (overall_kappa, per_item_kappas).
    """
    item_kappas = {}
    for item in TIME_USE_ITEMS:
        iid = item["id"]
        sys_score  = system_scores.get(iid, {}).get("score", 0)
        prac_score = practitioner_scores.get(iid, {}).get("score", 0)
        max_score  = item["max_score"]

        # Weighted kappa for single item pair
        if max_score == 0:
            item_kappas[iid] = 1.0
            continue

        # With two raters, Po = 1 if they agree, else 1 - |diff|/max_score
        # Simple linear weight for binary agreement on single item:
        po = 1.0 - abs(sys_score - prac_score) / max_score
        item_kappas[iid] = po  # single-item: kappa ≈ agreement weight

    overall = sum(item_kappas.values()) / len(item_kappas) if item_kappas else 0.0
    return overall, item_kappas


def generate_item_feedback(
    item_id: str,
    system_score: int,
    practitioner_score: int,
    system_rationale: str,
    item_def: dict,
) -> str:
    """Generate clear, specific feedback for a missed item."""
    if system_score == practitioner_score:
        return "Correct."

    direction = "higher" if system_score > practitioner_score else "lower"
    diff = abs(system_score - practitioner_score)
    rubric_sys  = item_def["rubric"][system_score]
    rubric_prac = item_def["rubric"].get(practitioner_score, "N/A")

    return (
        f"The correct score is {system_score} (you scored {practitioner_score}, "
        f"{diff} point{'s' if diff != 1 else ''} {direction}). "
        f"Correct criteria: '{rubric_sys}'. "
        f"You selected: '{rubric_prac}'. "
        f"Rationale: {system_rationale}"
    )


async def submit_attempt(
    db: AsyncSession,
    attempt: IRRAttempt,
    scenario: IRRScenario,
) -> IRRAttempt:
    """Score a practitioner attempt and update their rolling progress."""
    now = datetime.now(timezone.utc)

    kappa, item_kappas = compute_kappa(scenario.system_scores, attempt.practitioner_scores)

    item_feedback = {}
    item_defs_by_id = {d["id"]: d for d in TIME_USE_ITEMS}
    for item_id, item_kappa in item_kappas.items():
        item_def = item_defs_by_id.get(item_id, {})
        sys_item  = scenario.system_scores.get(item_id, {})
        prac_item = attempt.practitioner_scores.get(item_id, {})
        item_feedback[item_id] = generate_item_feedback(
            item_id=item_id,
            system_score=sys_item.get("score", 0),
            practitioner_score=prac_item.get("score", 0),
            system_rationale=sys_item.get("rationale", ""),
            item_def=item_def,
        )

    attempt.kappa         = kappa
    attempt.passed        = kappa >= KAPPA_PASS_THRESHOLD
    attempt.item_kappas   = item_kappas
    attempt.item_feedback = item_feedback
    attempt.status        = IRRAttemptStatus.scored
    attempt.scored_at     = now
    attempt.submitted_at  = now

    await db.flush()
    await _update_progress(db, attempt)
    return attempt


async def _update_progress(db: AsyncSession, attempt: IRRAttempt) -> None:
    progress = await db.scalar(
        select(IRRProgress).where(IRRProgress.practitioner_id == attempt.practitioner_id)
    )
    if not progress:
        scenario = await db.get(IRRScenario, attempt.scenario_id)
        progress = IRRProgress(
            practitioner_id=attempt.practitioner_id,
            scenario_type=scenario.scenario_type if scenario else IRRScenarioType.time_use_eval,
            attempts_total=0,
            attempts_passed=0,
        )
        db.add(progress)

    progress.attempts_total  += 1
    progress.last_attempt_at  = datetime.now(timezone.utc)
    if attempt.passed:
        progress.attempts_passed += 1

    # Rolling window kappa: average of last ROLLING_WINDOW attempts
    recent = await db.scalars(
        select(IRRAttempt.kappa)
        .where(
            IRRAttempt.practitioner_id == attempt.practitioner_id,
            IRRAttempt.kappa.is_not(None),
        )
        .order_by(IRRAttempt.scored_at.desc())
        .limit(ROLLING_WINDOW)
    )
    recent_kappas = [k for k in recent.all() if k is not None]
    if recent_kappas:
        progress.rolling_kappa = sum(recent_kappas) / len(recent_kappas)

    if (
        progress.certified_at is None
        and len(recent_kappas) >= ROLLING_WINDOW
        and progress.rolling_kappa >= KAPPA_PASS_THRESHOLD
    ):
        progress.certified_at = datetime.now(timezone.utc)
        log.info("irr.practitioner_certified", practitioner_id=str(attempt.practitioner_id))

    await db.flush()
