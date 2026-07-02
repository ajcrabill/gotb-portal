"""Time Use Evaluation IRR Simulator service — dynamic scenario generation
and scoring (M20).

Practitioners read a synthetic set of board MEETING MINUTES (not an agenda
— an agenda can't tell you how long anything took; minutes can, so that's
what this simulates) and classify each block of time into one of the
Effective School Boards time-use Activities, entering the number of
minutes they'd attribute to each Activity. The system already knows the
"true" minute allocation baked into the scenario; Cohen's-kappa-style
agreement is computed between the practitioner's minute entries and the
system's.

Classification is based ENTIRELY on what the board actually did with the
time — the description — never on the agenda item's title. An item
titled "Goal #1 Monitoring Session" whose description says the board
spent the time debating pizza vs. hamburgers for a staff lunch still
codes as "Other." _MINUTE_TEMPLATES intentionally includes several
title/description mismatches in both directions (a substantive-sounding
title over trivial content, and a bland title like "Old Business" over
real monitoring-calendar work) so the exercise actually tests reading
the description, not pattern-matching the label — see the "other" and
"guardrail_monitoring" template lists below for examples.

The Activity taxonomy below is transcribed verbatim (Framework, Activity,
Description) from the real ESB Board Monthly Time Use Evaluation form:
https://docs.google.com/spreadsheets/d/1dpA-RaO_3NyP_5VCcWFeWgphgot3mJjgpfh3PX9o1tY
(gid=1337581783, "Time Use Eval Form" tab — not the instructions tab).
Two Activities ("Community Listening", "Data Eval") appear twice with
identical description text, once under each Clarify Priorities framework
group (Vision & Goals vs Values & Guardrails) — disambiguated here by a
_goals / _guardrails suffix on the id, matching the source's own
structure rather than merging them.

Cohen's kappa formula:
  κ = (Po - Pe) / (1 - Pe)
  where Po = observed agreement, Pe = expected chance agreement.

  This simulator uses a simplified linear per-item agreement (Po only,
  no chance-correction term) averaged across items, same simplification
  the prior 0-4-rubric version used — noted here rather than silently
  changed. kappa >= 0.70 = reliable; < 0.40 = poor; 0.40-0.69 = moderate.
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

# ── Time Use Evaluation Activity taxonomy (verbatim from the source form) ────

TIME_USE_ITEMS = [
    {"id": "board_self_eval", "framework": "Focus Mindset", "label": "Board Self Eval",
     "description": "Quarterly and/or annual Board self-evaluation using the effective school boards framework instrument."},
    {"id": "effective_time_use_eval", "framework": "Focus Mindset", "label": "Effective Time Use Eval",
     "description": "Meeting evaluation using this time use instrument."},
    {"id": "board_training", "framework": "Focus Mindset", "label": "Board Training",
     "description": "Training for the Board on the effective school boards framework and related topics."},
    {"id": "board_led_community_training", "framework": "Focus Mindset", "label": "Board-led Community Training",
     "description": "Board-hosted and Board Member-led or co-led training on the effective school boards framework and related topics."},

    {"id": "community_listening_goals", "framework": "Clarify Priorities 1: Vision & Goals", "label": "Community Listening",
     "description": "Two-way communication opportunity where Board Members listen for and discuss the vision/values of their students, families, staff and community members — related to the community's vision, setting Goals, and/or monitoring Goals."},
    {"id": "data_eval_goals", "framework": "Clarify Priorities 1: Vision & Goals", "label": "Data Eval",
     "description": "Analyzing student data that speaks to the highest need, highest leverage areas."},
    {"id": "goal_setting", "framework": "Clarify Priorities 1: Vision & Goals", "label": "Goal Setting",
     "description": "Learning, data gathering, reviewing, discussing, and/or selecting goals and accepting interim goals."},

    {"id": "community_listening_guardrails", "framework": "Clarify Priorities 2: Values & Guardrails", "label": "Community Listening",
     "description": "Two-way communication opportunity where Board Members listen for and discuss the vision/values of their students, families, staff and community members — related to setting and/or monitoring Guardrails."},
    {"id": "data_eval_guardrails", "framework": "Clarify Priorities 2: Values & Guardrails", "label": "Data Eval",
     "description": "Analyzing system data that speaks to the highest need, highest leverage areas."},
    {"id": "guardrail_setting", "framework": "Clarify Priorities 2: Values & Guardrails", "label": "Guardrail Setting",
     "description": "Learning, data gathering, reviewing, discussing, and/or selecting guardrails and accepting interim guardrails."},

    {"id": "goal_monitoring", "framework": "Monitor Progress", "label": "Goal Monitoring",
     "description": "Learning, data gathering, reviewing, discussing, and/or approving/not approving goal monitoring reports in accordance with the monitoring calendar."},
    {"id": "guardrail_monitoring", "framework": "Monitor Progress", "label": "Guardrail Monitoring",
     "description": "Learning, data gathering, reviewing, discussing, and/or approving/not approving guardrail monitoring reports in accordance with the monitoring calendar."},
    {"id": "superintendent_eval", "framework": "Monitor Progress", "label": "Superintendent Eval",
     "description": "Annual evaluation of Superintendent/school system performance."},

    {"id": "voting", "framework": "Align Resources", "label": "Voting",
     "description": "The Board debating and/or voting on any item. Voting on goal/guardrail adoption and/or scheduled monitoring reports & evals are counted elsewhere, not here — all other incidents of debating/voting are never a form of goals/guardrails “monitoring.”"},
    {"id": "policy_review", "framework": "Align Resources", "label": "Policy Review/Diet",
     "description": "The Board evaluating whether policies align with the goals, guardrails, or legal requirements."},
    {"id": "budget_review", "framework": "Align Resources", "label": "Budget Review",
     "description": "The Board evaluating whether the budget aligns with the goals and guardrails."},

    {"id": "community_engagement", "framework": "Communicate Results", "label": "Community Engagement",
     "description": "Two-way communication opportunity hosted by Board Members where they listen for and discuss the vision/values of their students, families, staff and community members, related to board work, but that is NOT setting or monitoring goals and guardrails. Must be genuinely two-way and board-hosted — a one-way public comment period where the board listens without dialogue does not meet this definition; that time is “Other.”"},
    {"id": "community_outreach", "framework": "Communicate Results", "label": "Community Outreach",
     "description": "Two-way communication opportunity where Board Members go to community-hosted meetings to listen for and discuss the vision/values of their students, families, staff and community members, related to board work, but that is NOT setting or monitoring goals or guardrails. Must be genuinely two-way — the board attending and passively observing a community event does not meet this definition."},

    {"id": "closed_session", "framework": "Other", "label": "Closed Session",
     "description": "Time spent in non-public meetings, consistent with open meetings laws. Not counted in Total Public Meeting Minutes.",
     "excluded_from_totals": True},
    {"id": "other", "framework": "Other", "label": "Other",
     "description": "Any time spent on an activity that is not one of the above — including one-way public comment periods, procedural items (call to order, roll call, adjournment), and consent-agenda approval that isn't itself a Voting deliberation."},
]

_ITEMS_BY_ID = {i["id"]: i for i in TIME_USE_ITEMS}
_STUDENT_OUTCOMES_IDS = {"goal_setting", "goal_monitoring"}  # per the source form's own formula


# ── Narrative minute-block templates ─────────────────────────────────────────
# Each entry is a list of (agenda_item_title, text_template, minutes_range)
# tuples for one activity id. Real minutes are organized under short
# agenda-item headers (the title), with the narrative of what actually
# happened recorded underneath — so each block shows both. The title alone
# is often ambiguous (e.g. "Public Comment" could sound like Community
# Engagement) — several descriptions are written to be genuinely close
# calls that only resolve correctly against the Activity descriptions
# above (that's deliberate: reading the description is supposed to
# matter, not just pattern-matching the item title).

_MINUTE_TEMPLATES: dict[str, list[tuple[str, str, tuple[int, int]]]] = {
    "other": [
        ("Call to Order / Roll Call", "The board president called the meeting to order at 6:00 PM and the secretary called roll; {quorum} of {board_size} members were present.", (2, 4)),
        ("Pledge of Allegiance", "The meeting opened with the Pledge of Allegiance, led by a student representative from {school}.", (1, 2)),
        ("Approval of Minutes", "The board reviewed and approved the minutes from the previous regular meeting without discussion.", (1, 3)),
        ("Approval of Agenda", "The board voted to approve the evening's agenda as printed, with one item moved up at a member's request.", (1, 2)),
        ("Public Comment", "During the public comment period, {n_speakers} community members addressed the board on topics including a proposed bus route change and a maintenance complaint at {school}. Each speaker had three minutes at the podium; board members thanked speakers for their comments but did not respond to or discuss any of the concerns raised, and no board member engaged in dialogue with a speaker.", (8, 22)),
        ("Public Comment", "The board took public comment on the district's dress code policy. Twelve parents signed up; the board chair reminded the room that per policy the board does not respond during public comment, and none did. Comments were read into the record by the clerk.", (10, 18)),
        ("Public Comment", "During public comment, {n_speakers} teachers spoke about staffing shortages at {school}. The board listened, thanked the speakers, and moved to the next agenda item without discussion or follow-up questions.", (6, 15)),
        ("Consent Agenda", "The board approved the consent agenda in a single motion, covering routine items including field trip approvals, facility use requests, and personnel notifications, with no discussion.", (2, 5)),
        ("Recognition of Students", "The board recognized the {school} robotics team for placing first at the state competition, presenting certificates; no discussion of governance matters occurred.", (3, 8)),
        ("Recognition of Staff", "The board recognized a retiring teacher of 30 years with a plaque and brief remarks from the superintendent.", (2, 5)),
        ("Superintendent's Announcements", "The superintendent gave a general update on district happenings — upcoming testing windows, a facilities walkthrough, and a reminder about the winter concert schedule — with no board discussion or action.", (3, 8)),
        ("Correspondence", "The board secretary read into the record a list of correspondence received since the last meeting; no action was taken.", (1, 3)),
        ("Adjournment", "The meeting was adjourned at the board president's motion, seconded and approved unanimously.", (1, 2)),
        # Deliberately misleading titles — the item name suggests a
        # substantive Activity, but what the board actually did during
        # that time doesn't meet the Activity's definition. Coding is
        # always based on the description, never the title.
        ("Goal #1 Monitoring Session", "The board discussed whether to have pizza or hamburgers at next month's staff appreciation lunch before moving on to the next item.", (3, 8)),
        ("Superintendent Evaluation", "The item was listed on the agenda, but the board ran out of time and voted to postpone the discussion to next month without any substantive conversation.", (1, 3)),
        ("Student Achievement Update", "The board received a one-page handout summarizing recent test scores. No board member asked a question or commented, and the board moved immediately to the next item.", (2, 5)),
        ("Goal Progress Report", "The item was announced but the presenter had technical difficulties with their slides; after several minutes of troubleshooting, the board agreed to reschedule the report for next month.", (4, 9)),
        ("Community Engagement Update", "A board member gave a two-minute verbal summary that they had personally visited a school open house earlier in the week; no discussion followed and no board action was taken.", (2, 4)),
    ],
    "board_self_eval": [
        ("Board Self-Evaluation", "The board conducted its quarterly self-evaluation using the Effective School Boards framework instrument, with each member independently scoring the board's performance on Focus Mindset and Clarify Priorities before discussing results as a group.", (15, 30)),
        ("Annual Governance Self-Assessment", "As required by board bylaws, members completed the annual governance self-assessment survey together, discussing areas where the board rated itself lowest and what might explain the gap.", (20, 35)),
        ("Mid-Year Governance Check-In", "The board paused to reflect on its own performance against its adopted norms for the year, with the board chair facilitating a discussion of what's working and what isn't in how the board conducts its business.", (10, 20)),
    ],
    "effective_time_use_eval": [
        ("Time Use Evaluation Review", "The board reviewed last month's time-use evaluation results, comparing the percentage of the prior meeting spent on student-outcomes-focused work against the board's own target.", (5, 12)),
        ("Monthly Time Use Debrief", "Using the completed time-use evaluation form from the previous meeting, the board discussed why goal-focused minutes fell short of the 50% target and what adjustments to make to this month's agenda.", (8, 15)),
    ],
    "board_training": [
        ("Board Development: Governance vs. Management", "A board development consultant led a training session for board members on distinguishing governance from management, using recent board decisions as case studies.", (20, 45)),
        ("Guardrail Monitoring Calendar Review", "The board spent time reviewing the Effective School Boards framework's guardrail-monitoring calendar and discussing how upcoming reports would be structured.", (10, 20)),
        ("New Member Orientation", "The board's newest member received training from a veteran board member on the district's SMART goal framework and how monitoring reports are structured, using real examples from the past year.", (15, 30)),
        ("Legal Update Training", "District legal counsel trained the board on updated open-meetings law requirements and how they affect closed-session procedures.", (15, 25)),
        ("Effective Governance Refresher", "At the board chair's request, the district's ESB-certified practitioner led a refresher session on the difference between adult inputs and student outcomes, using a recent board vote as a discussion case.", (15, 30)),
    ],
    "board_led_community_training": [
        ("Community Workshop: SMART Goals", "As a scheduled agenda item, two board members co-led a community workshop segment of the meeting, walking attendees through the district's SMART goal framework and how the community can track progress.", (20, 40)),
        ("Understanding the Budget: Community Session", "As a formal segment of tonight's meeting, board members walked attendees through how to read the district's budget documents and where to find the numbers tied to adopted goals.", (20, 35)),
        ("Governance 101 for Families", "Board members led a portion of the meeting explaining, for newer community members in attendance, what the board does versus what the superintendent does and why that distinction matters for accountability.", (15, 25)),
    ],
    "community_listening_goals": [
        ("Community Listening: Student Outcome Priorities", "Board members broke into small groups with attendees to gather input on what families believe the district's top student-outcome priority should be for next year, with each group reporting themes back to the full board.", (15, 30)),
        ("Structured Listening Session: District Vision", "The board held a structured listening session, asking attendees direct questions about their vision for the district and taking notes on responses that will inform the upcoming goal-setting cycle; several board members asked follow-up questions of specific speakers.", (15, 25)),
        ("Listening Session: College and Career Readiness", "The board asked attendees in the room what they believe college and career readiness should look like for graduates, discussing the range of answers as input for the next goal-setting cycle.", (12, 20)),
        ("Family Input: Literacy Priorities", "As a structured agenda item, the board invited attendees to share what a successful reader looks like to them at each grade band, with board members asking clarifying follow-up questions to several speakers.", (15, 28)),
    ],
    "data_eval_goals": [
        ("Student Data Review: Reading Assessment", "The board reviewed disaggregated third-grade reading assessment data by subgroup, discussing which student populations showed the largest gaps against the district's literacy goal.", (10, 25)),
        ("Graduation Rate Data Presentation", "The academic officer presented graduation-rate trend data over the last five years, and board members asked clarifying questions about which cohorts were most at risk of not graduating on time.", (12, 20)),
        ("Chronic Absenteeism Data Review", "The board reviewed chronic absenteeism data broken down by grade level and campus, discussing which schools showed the sharpest increases and what that might mean for the district's attendance goal.", (10, 20)),
        ("Math Proficiency Trend Analysis", "The board examined three years of state math assessment data by subgroup, asking pointed questions about why growth had stalled among English language learners relative to the district's stated goal.", (12, 25)),
        ("Career Readiness Indicator Review", "The board reviewed data on industry certification attainment and dual-enrollment participation, discussing whether current rates put the district on track for its college-and-career-readiness goal.", (10, 18)),
    ],
    "goal_setting": [
        ("Interim Goal: Third-Grade Reading Proficiency", "The board discussed and voted to accept an interim goal for third-grade reading proficiency, setting a target of increasing the percentage of students reading on grade level from 45% to 55% by the end of the school year.", (10, 25)),
        ("Goal Adoption: Graduation Rate", "Following a first read at the prior meeting, the board formally adopted its five-year student-outcomes goal on graduation rate, setting a target increase from 78% to 90% by 2030.", (8, 18)),
        ("Interim Goal: Chronic Absenteeism Reduction", "The board discussed and voted to accept a new interim goal to reduce the chronic absenteeism rate from 18% to 12% by the end of the school year, following a presentation of the underlying data.", (10, 20)),
        ("Goal Adoption: Math Proficiency", "The board formally adopted a three-year SMART goal to increase the percentage of students scoring proficient on the state math assessment from 52% to 68% by spring 2029.", (10, 20)),
        ("Interim Goal: College and Career Readiness", "After extended discussion of what indicators to use, the board voted to accept an interim goal increasing the percentage of graduates earning an industry certification or college credit from 30% to 45% within two years.", (12, 22)),
    ],
    "community_listening_guardrails": [
        ("Community Values Discussion", "During the public meeting, the board asked attendees in the room what non-negotiable community values the board should protect when it comes to how the superintendent operates, and discussed the themes that emerged.", (15, 25)),
        ("Guardrail Input Session", "As a structured portion of the meeting, the board asked families in attendance what boundaries they believe the superintendent should never cross when making discipline decisions, and discussed the responses as a board.", (15, 25)),
        ("Community Values: Facility Safety", "The board invited attendees to share what they consider non-negotiable when it comes to campus safety procedures, with board members asking follow-up questions to understand specific concerns raised.", (12, 20)),
    ],
    "data_eval_guardrails": [
        ("Discipline Data Review", "The board reviewed discipline-incident data broken out by school and by student subgroup, looking for patterns that might indicate a guardrail violation around equitable discipline practices.", (10, 20)),
        ("Special Education Compliance Data", "The board reviewed data on special education service delivery timelines, discussing whether any campus showed patterns that could put the district out of compliance with its guardrail on legally required services.", (10, 18)),
        ("Staff Discipline and Grievance Data", "The board examined a summary of staff grievances filed over the past quarter, discussing whether the pattern suggested any guardrail around fair employment practices was at risk.", (8, 15)),
    ],
    "guardrail_setting": [
        ("Guardrail Adoption: Curriculum Change Process", "The board discussed and adopted a new guardrail prohibiting the superintendent from approving any curriculum change without first engaging classroom teachers, following board discussion of a proposed contract that had already drawn teacher objections.", (10, 20)),
        ("Guardrail Adoption: Discipline Practices", "Following community concerns raised at prior meetings, the board debated and adopted a guardrail prohibiting the superintendent from suspending elementary students for non-violent offenses without exhausting alternative interventions first.", (12, 22)),
        ("Guardrail Adoption: Facility Safety Standards", "The board discussed and adopted a guardrail requiring the superintendent to ensure every campus completes a safety drill within the first 30 days of each semester.", (10, 18)),
    ],
    "goal_monitoring": [
        ("Quarterly Goal Monitoring Report: Math Proficiency", "The superintendent presented the scheduled quarterly goal-monitoring report on the district's math proficiency goal, showing current performance against the interim target; the board discussed the data and voted to accept the report as presented.", (15, 30)),
        ("Semi-Annual Goal Monitoring Report: Graduation Rate", "Per the monitoring calendar, the board reviewed the semi-annual graduation-rate goal report, asked the superintendent several questions about the plan to close the gap with the target, and voted not to accept the report pending additional data.", (15, 25)),
        ("Monthly Goal Monitoring Report: Chronic Absenteeism", "As scheduled on the monitoring calendar, the superintendent presented the monthly attendance goal report; the board discussed whether the current intervention plan was sufficient to hit the year-end target and voted to accept the report.", (12, 22)),
        ("Goal Monitoring Report: Third-Grade Reading", "The board reviewed the scheduled interim report on third-grade reading proficiency, comparing current benchmark data against the adopted target, and voted to accept the report while directing the superintendent to bring more detail on the lowest-performing campus next month.", (15, 28)),
        ("Goal Monitoring Report: College and Career Readiness", "Per the monitoring calendar, the superintendent presented the annual goal report on industry certification and dual-enrollment rates; the board discussed the trend line and voted to accept the report as presented.", (12, 20)),
    ],
    "guardrail_monitoring": [
        ("Guardrail Monitoring Report: Student Discipline", "The board reviewed the scheduled guardrail-monitoring report on student discipline practices, comparing suspension rates by subgroup against the guardrail's non-negotiable language, and voted to accept the report.", (10, 20)),
        ("Guardrail Monitoring Report: Community Engagement Compliance", "As scheduled on the monitoring calendar, the superintendent presented evidence of compliance with the community-engagement guardrail, and the board discussed whether the evidence provided was sufficient before voting to accept it.", (10, 18)),
        ("Guardrail Monitoring Report: Special Education Timelines", "Per the monitoring calendar, the superintendent presented evidence that all special education evaluation timelines were met this quarter; the board discussed one flagged exception and voted to accept the report with a follow-up requested.", (10, 20)),
        ("Guardrail Monitoring Report: Facility Safety", "The board reviewed the scheduled report on campus safety drill compliance, comparing results against the guardrail's requirements campus by campus, and voted to accept the report.", (10, 18)),
        # Reverse mismatch: a bland, unrevealing title hiding real
        # monitoring-calendar work — the description is still what codes it.
        ("Old Business", "Under old business, the superintendent presented the scheduled evidence report on the community-engagement guardrail per the monitoring calendar, and the board voted to accept it.", (10, 18)),
        ("Item 12", "Per the monitoring calendar, the superintendent presented the scheduled report on discipline-guardrail compliance, and after board discussion of one flagged incident, the board voted to accept the report.", (10, 20)),
    ],
    "superintendent_eval": [
        ("Superintendent Annual Performance Evaluation", "The board conducted the superintendent's annual performance evaluation in open session, with each board member sharing scored feedback against the adopted evaluation rubric before reaching consensus on an overall rating.", (25, 50)),
        ("Superintendent Mid-Year Check-In", "The board conducted a scheduled mid-year evaluation check-in with the superintendent, discussing progress against the goals set at the start of the year and any concerns raised by individual board members.", (15, 30)),
        ("Superintendent Contract Renewal Discussion", "As part of the formal evaluation cycle, the board discussed the superintendent's performance over the past year as the basis for an upcoming contract renewal decision.", (20, 35)),
    ],
    "voting": [
        ("Attendance Boundary Change", "The board debated and voted on a proposed change to the district's attendance boundary lines, with several members raising concerns about impact on specific neighborhoods before the motion passed 4-3.", (10, 25)),
        ("Transportation Services Contract", "The board voted to approve a new vendor contract for transportation services after brief discussion of the bid comparison.", (5, 12)),
        ("Bond Referendum Resolution", "The board voted to place a facilities bond referendum on the next election ballot, after discussion of the proposed dollar amount and project list.", (10, 20)),
        ("Redistricting Plan Adoption", "Following months of community meetings, the board voted 5-2 to adopt a revised attendance-zone map, with dissenting members citing concerns about specific neighborhoods.", (15, 25)),
        ("Superintendent Contract Amendment", "The board voted to approve an amendment to the superintendent's contract extending the term by two years, after brief discussion.", (5, 12)),
        ("Athletic Facility Naming", "The board voted to approve naming the new stadium after a longtime donor, following a brief presentation from the naming committee.", (3, 8)),
        # Mismatch: sounds like Budget Review, but there's no evaluation of
        # whether the budget aligns with goals/guardrails — just a vote.
        ("Budget Discussion", "Without discussion of whether the numbers aligned with any adopted goal or guardrail, the board voted 5-0 to approve the annual budget as presented.", (3, 8)),
    ],
    "policy_review": [
        ("Policy 123 - First Read", "The board conducted a first reading of a revised student code of conduct policy, discussing whether the proposed language aligned with the district's adopted guardrails on discipline.", (10, 20)),
        ("Open-Records Policy Update", "Legal counsel walked the board through required updates to the district's open-records policy to remain compliant with a recent state law change, and the board discussed whether the update conflicted with any existing guardrail.", (8, 15)),
        ("Cell Phone Policy Review", "The board reviewed a proposed revision to the student cell phone policy, discussing whether the language was consistent with the board's adopted guardrails on classroom instructional time.", (12, 22)),
        ("Attendance Policy Alignment Review", "The board evaluated whether the district's current attendance policy supported or worked against its adopted chronic-absenteeism goal, directing staff to bring revised language next month.", (10, 18)),
        ("Special Education Policy Update", "The board reviewed proposed updates to special education referral policy to ensure alignment with both state requirements and the board's adopted guardrail on service timelines.", (10, 20)),
    ],
    "budget_review": [
        ("Mid-Year Budget Forecast", "The chief financial officer presented the mid-year budget forecast, and the board discussed whether proposed reallocations toward literacy intervention staffing aligned with the district's adopted goals.", (12, 25)),
        ("Budget Proposal", "The board reviewed the proposed capital budget for facility repairs, discussing whether the prioritized projects reflected the guardrails around equitable facility conditions across schools.", (15, 25)),
        ("Bond Fund Allocation Review", "The board evaluated whether the proposed use of bond proceeds for a new STEM wing aligned with the district's adopted college-and-career-readiness goal.", (12, 22)),
        ("Staffing Budget Alignment", "The finance office presented the proposed staffing budget, and the board discussed whether proposed reading-specialist positions were sufficiently funded to support the district's literacy goal.", (10, 20)),
        ("Technology Budget Review", "The board reviewed the proposed technology budget, evaluating whether device replacement priorities aligned with the guardrail on equitable access across campuses.", (10, 18)),
    ],
    "community_engagement": [
        ("Community Engagement Session", "The board hosted a structured community forum on the district's proposed rezoning plan, with board members taking questions directly from attendees and engaging in back-and-forth discussion about specific concerns raised, including several instances of a board member following up on a speaker's point.", (20, 40)),
        ("Coffee with the Board", "As a scheduled segment of tonight's meeting, board members held a \"Coffee with the Board\" question period, fielding questions from roughly twenty attendees in the room about the district's strategic priorities and responding directly to each question asked.", (15, 30)),
        ("Community Forum: Bond Referendum", "As part of tonight's meeting, the board hosted an open Q&A on the proposed facilities bond, with board members responding directly to concerns about tax impact and project prioritization raised by attendees.", (20, 35)),
        ("Town Hall Segment: Redistricting Feedback", "As a formal segment of the meeting, the board opened the floor for real-time dialogue on the proposed boundary map, with board members responding to specific concerns and asking clarifying questions of several speakers.", (25, 40)),
    ],
    # NOTE: "community_outreach" is intentionally NOT in this dict.
    # Community Outreach is, by the Activity's own definition, board
    # members attending a COMMUNITY-hosted meeting somewhere else — it
    # cannot happen "during" a single board meeting's own minutes. A
    # board member reporting during this meeting on an outreach event
    # they previously attended is a report-back (that reporting time
    # would code elsewhere, e.g. Other), not the outreach itself. The
    # Activity stays in the scored rubric (TIME_USE_ITEMS /
    # ACTIVITY_ITEMS) so practitioners see it and correctly enter 0 for
    # any single-meeting scenario — it's just never fabricated as a
    # same-meeting minute-block. See AJ's correction, 2026-07-02.
    "closed_session": [
        ("Executive Session: Litigation", "The board entered closed session, consistent with open meetings law, to discuss active litigation; the meeting resumed in open session with no action taken.", (15, 40)),
        ("Executive Session: Superintendent Contract", "The board convened in executive session to discuss the superintendent's contract renewal terms before returning to open session to vote.", (20, 45)),
        ("Executive Session: Personnel Matter", "The board entered closed session to discuss a personnel matter involving a campus administrator, consistent with open meetings law exceptions; no action was taken upon returning to open session.", (15, 35)),
        ("Executive Session: Real Estate Negotiation", "The board convened in executive session to discuss the potential purchase of land for a future school site, returning to open session to authorize continued negotiation.", (20, 40)),
    ],
}

_SCHOOLS = ["Jefferson Elementary", "Lincoln Middle School", "Roosevelt High School", "Washington Elementary", "Kennedy Middle School"]


def _seed_from_string(s: str) -> int:
    return int(hashlib.md5(s.encode()).hexdigest(), 16) % (2**31)


def _random_date_near_today(rng: random.Random) -> str:
    days_ago = rng.randint(7, 120)
    d = date.today() - timedelta(days=days_ago)
    return d.strftime("%B %d, %Y")


def _generate_minute_items(rng: random.Random, quorum: int, board_size: int) -> list[dict]:
    """Generate a synthetic set of meeting-minutes entries — narrative
    descriptions of what the board did during each time block, each tagged
    (internally, not shown to the practitioner) with the ground-truth
    Activity id it should be classified as."""
    # Always include the routine "Other" procedural items (call to order,
    # minutes approval, public comment, consent agenda, adjournment) —
    # every real meeting has these, and public comment belongs in Other
    # per the corrected definition, not Community Engagement.
    other_pool = _MINUTE_TEMPLATES["other"]
    selected_other = rng.sample(other_pool, k=min(len(other_pool), rng.randint(4, 6)))

    # Then a random selection of substantive activities.
    substantive_ids = [k for k in _MINUTE_TEMPLATES if k != "other"]
    chosen_ids = rng.sample(substantive_ids, k=rng.randint(5, 9))

    items: list[dict] = []
    for title, text_template, minutes_range in selected_other:
        items.append(_fill_item(rng, "other", title, text_template, minutes_range, quorum, board_size))
    for activity_id in chosen_ids:
        title, text_template, minutes_range = rng.choice(_MINUTE_TEMPLATES[activity_id])
        items.append(_fill_item(rng, activity_id, title, text_template, minutes_range, quorum, board_size))

    rng.shuffle(items)
    return items


def _fill_item(rng: random.Random, activity_id: str, title: str, template: str, minutes_range: tuple[int, int], quorum: int, board_size: int) -> dict:
    minutes = rng.randint(*minutes_range)
    text = template.format(
        quorum=quorum, board_size=board_size,
        n_speakers=rng.randint(3, 9), school=rng.choice(_SCHOOLS),
    )
    return {"title": title, "description": text, "activity_id": activity_id, "minutes": minutes}


_DISTRICTS = [
    "Riverside Unified School District",
    "Northlake Community School District",
    "Elmwood Independent School District",
    "Clearwater Public Schools",
    "Hillcrest School District",
    "Mapleton Unified School District",
    "Cedar Falls Public Schools",
    "Brookhaven Independent School District",
    "Sunridge Unified School District",
    "Pinecrest Community School District",
    "Fairview Public Schools",
    "Silver Creek Unified School District",
    "Oakmont Independent School District",
    "Meadowbrook School District",
    "Harborview Public Schools",
    "Stonebridge Unified School District",
    "Willow Grove Community School District",
    "Ridgeline Independent School District",
    "Copper Valley School District",
    "Bayside Unified School District",
    "Prairie View Public Schools",
    "Ashford Independent School District",
    "Crestwood Community School District",
    "Lakeshore Unified School District",
    "Timberline Public Schools",
    "Foxborough Independent School District",
    "Granite Hills School District",
    "Magnolia Unified School District",
    "Sagebrush Community School District",
    "Whitmore Independent School District",
]


def generate_scenario(
    scenario_type: IRRScenarioType = IRRScenarioType.time_use_eval,
    seed: str | None = None,
) -> dict:
    """Generate synthetic scenario data — a set of meeting-minutes entries
    (not an agenda) with narrative descriptions the practitioner must
    classify and time. Returns a dict with everything needed to present
    the scenario."""
    if seed is None:
        seed = secrets.token_hex(8)
    rng = random.Random(_seed_from_string(seed))

    meeting_date = _random_date_near_today(rng)
    district_name = rng.choice(_DISTRICTS)
    board_size = rng.randint(5, 7)
    quorum = rng.randint(board_size - 1, board_size)

    minute_items = _generate_minute_items(rng, quorum, board_size)
    total_minutes = sum(m["minutes"] for m in minute_items)

    return {
        "district": district_name,
        "meeting_date": meeting_date,
        "meeting_type": rng.choice(["Regular Board Meeting", "Special Board Meeting"]),
        "quorum_present": quorum,
        "board_size": board_size,
        "total_minutes": total_minutes,
        # activity_id (the ground-truth classification) is withheld from the
        # practitioner — that's the thing being tested. Duration is not a
        # secret: real meeting minutes always show how long each item took,
        # and without it there's no way to total minutes per Activity at all.
        "minute_items": [{"title": m["title"], "description": m["description"], "minutes": m["minutes"]} for m in minute_items],
        "_minute_items_truth": minute_items,  # includes activity_id; stripped before sending to client
        "notes": (
            f"The board convened at 6:00 PM with {quorum} of {board_size} members present. "
            f"Total meeting time: {total_minutes} minutes."
        ),
    }


def system_score_scenario(scenario_data: dict) -> dict:
    """Apply the canonical scoring to a generated scenario: sum the
    ground-truth minutes per Activity. Returns {item_id: {minutes, pct_of_meeting}}
    for all Activities (0 minutes for ones that didn't occur)."""
    truth_items = scenario_data.get("_minute_items_truth") or []
    total = scenario_data.get("total_minutes", 0) or 1

    minutes_by_activity: dict[str, int] = {i["id"]: 0 for i in TIME_USE_ITEMS}
    for m in truth_items:
        aid = m.get("activity_id", "other")
        minutes_by_activity[aid] = minutes_by_activity.get(aid, 0) + m["minutes"]

    scores = {}
    for item in TIME_USE_ITEMS:
        iid = item["id"]
        mins = minutes_by_activity.get(iid, 0)
        scores[iid] = {
            "minutes": mins,
            "pct_of_meeting": round((mins / total) * 100, 1),
        }

    student_outcomes_minutes = sum(minutes_by_activity.get(i, 0) for i in _STUDENT_OUTCOMES_IDS)
    public_meeting_minutes = sum(
        mins for iid, mins in minutes_by_activity.items()
        if not _ITEMS_BY_ID.get(iid, {}).get("excluded_from_totals")
    )
    scores["_totals"] = {
        "student_outcomes_minutes": student_outcomes_minutes,
        "student_outcomes_pct": round((student_outcomes_minutes / total) * 100, 1),
        "public_meeting_minutes": public_meeting_minutes,
    }
    return scores


def compute_kappa(system_scores: dict, practitioner_scores: dict) -> tuple[float, dict]:
    """Per-item agreement (Po, no chance-correction — same simplification
    the prior 0-4-rubric version used) comparing entered minutes, not a
    selected band. Normalized against total meeting minutes so a miss of
    the whole meeting length floors agreement at 0 for that item.

    Only Activities that were actually "in play" — the system recorded
    minutes for it, the practitioner did, or both — count toward the
    average. With ~20 Activities and typically only 8-13 occurring in a
    given scenario, averaging over all 20 (most trivially 0/0) let a
    practitioner who entered nothing score ~0.94 by free-riding on the
    Activities that never came up. Scoring only the ones in play measures
    what the instrument is actually meant to measure: did the
    practitioner correctly classify and time the things that happened.
    An item_kappas entry is still returned for every Activity (0/0 items
    get a full-credit 1.0, shown but excluded from the average) so the
    UI can show per-item feedback across the whole rubric."""
    total_minutes = system_scores.get("_totals", {}).get("public_meeting_minutes") or 1
    item_kappas = {}
    in_play_scores = []
    for item in TIME_USE_ITEMS:
        iid = item["id"]
        sys_minutes  = system_scores.get(iid, {}).get("minutes", 0)
        prac_minutes = practitioner_scores.get(iid, {}).get("minutes", 0)

        diff = abs(sys_minutes - prac_minutes)
        po = 1.0 - min(diff, total_minutes) / total_minutes
        item_kappas[iid] = po
        if sys_minutes > 0 or prac_minutes > 0:
            in_play_scores.append(po)

    overall = sum(in_play_scores) / len(in_play_scores) if in_play_scores else 1.0
    return overall, item_kappas


def generate_item_feedback(
    item_id: str,
    system_minutes: int,
    practitioner_minutes: int,
    item_def: dict,
) -> str:
    """Generate clear, specific feedback for a missed item."""
    if system_minutes == practitioner_minutes:
        return "Correct."

    diff = abs(system_minutes - practitioner_minutes)
    direction = "more" if system_minutes > practitioner_minutes else "fewer"
    return (
        f"The correct total is {system_minutes} minute{'s' if system_minutes != 1 else ''} "
        f"(you entered {practitioner_minutes}, {diff} {direction}). "
        f"'{item_def.get('label', item_id)}' ({item_def.get('framework', '')}): {item_def.get('description', '')}"
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
    for item_id, item_kappa in item_kappas.items():
        item_def = _ITEMS_BY_ID.get(item_id, {})
        sys_item  = scenario.system_scores.get(item_id, {})
        prac_item = attempt.practitioner_scores.get(item_id, {})
        item_feedback[item_id] = generate_item_feedback(
            item_id=item_id,
            system_minutes=sys_item.get("minutes", 0),
            practitioner_minutes=prac_item.get("minutes", 0),
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
