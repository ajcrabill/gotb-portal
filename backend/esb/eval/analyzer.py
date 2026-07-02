"""LLM-powered analysis pipeline using OpenRouter.

Ported from esby-portal's app/analyzer.py.
"""
import json
from typing import Any, Dict, List

import httpx

from esb.core.config import settings
from esb.eval.classification_guide import CLASSIFICATION_GUIDE

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "deepseek/deepseek-r1-0528"


async def _chat(messages: List[Dict], temperature: float = 0.2) -> str:
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": "https://gotb.effectiveschoolboards.com",
        "X-Title": "ESB Portal",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 4096,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(OPENROUTER_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"]


def _strip_json_fence(result: str) -> str:
    result = result.strip()
    if result.startswith("```"):
        result = result.split("```")[1]
        if result.startswith("json"):
            result = result[4:]
    return result.strip()


async def extract_agenda_items(transcript: str, district: str, meeting_date: str) -> List[Dict]:
    """Extract agenda items with time estimates from transcript."""
    prompt = f"""You are analyzing a school board meeting transcript for {district} ({meeting_date}).

Extract each distinct agenda item discussed in this meeting. For each item provide:
- item_number: sequential number
- title: brief title (5-10 words)
- description: what happened (2-3 sentences)
- estimated_minutes: your best estimate of time spent (integer)
- speakers: list of roles who spoke (Board Member, Superintendent, Staff, Public, etc.)

The items should be in order and cover the entire meeting.

TRANSCRIPT:
{transcript[:12000]}

Respond with a JSON array only, no other text:
[{{"item_number": 1, "title": "...", "description": "...", "estimated_minutes": 5, "speakers": ["Board Member"]}}]"""

    result = await _chat([{"role": "user", "content": prompt}])
    return json.loads(_strip_json_fence(result))


async def classify_agenda_items(items: List[Dict], guide_text: str | None = None) -> List[Dict]:
    """Classify each agenda item using the ESB classification guide.

    guide_text defaults to the static CLASSIFICATION_GUIDE, but callers
    should pass the compiled guide (base doc + practitioner-submitted
    learning rules — see classification_guide.render_with_rules) so
    corrections filed from the IRR Simulator actually inform real
    evaluations, not just training scenarios."""
    items_text = "\n".join(
        f"{i['item_number']}. {i['title']}: {i['description']} (~{i['estimated_minutes']} min)"
        for i in items
    )

    prompt = f"""You are an ESB framework expert. Classify each agenda item using the classification guide below.

{guide_text or CLASSIFICATION_GUIDE}

AGENDA ITEMS TO CLASSIFY:
{items_text}

For each item, assign:
- item_number: matches input
- category: exactly one of: Goal Setting, Goal Monitoring, Guardrail Setting, Guardrail Monitoring, Data Evaluation (Student Data), Data Evaluation (System Data), Superintendent Evaluation, Community Listening (Goals), Community Listening (Guardrails), Policy Review, Budget Review, Board Self Evaluation, Board Training, Voting / Non-Goal Actions, Closed Session, Other
- minutes: integer (from input estimate)
- notes: one sentence explaining the classification
- goal_focused: true ONLY if category is "Goal Setting" or "Goal Monitoring"

Apply the decision tree rigorously. When in doubt, choose the non-Goal-Focused category.

Respond with JSON array only:
[{{"item_number": 1, "category": "Other", "minutes": 5, "notes": "...", "goal_focused": false}}]"""

    result = await _chat([{"role": "user", "content": prompt}])
    return json.loads(_strip_json_fence(result))


async def generate_coaching_reflections(
    items: List[Dict],
    classified: List[Dict],
    district: str,
    total_minutes: int,
    goal_focused_minutes: int,
) -> Dict[str, List[Dict]]:
    """Generate Practitioner Celebrates and Practitioner Recommends sections."""
    goal_pct = round(goal_focused_minutes / total_minutes * 100, 1) if total_minutes else 0

    summary = f"District: {district}\nTotal meeting time: {total_minutes} min\n"
    summary += f"Goal-focused time: {goal_focused_minutes} min ({goal_pct}%)\n\n"
    summary += "Key items:\n"
    for item, cls in zip(items[:15], classified[:15]):
        summary += f"- {item['title']} ({cls['minutes']} min, {cls['category']})\n"

    prompt = f"""You are AJ Crabill, an ESB (Effective School Boards) Certified Great on Their Behalf Practitioner writing coaching reflections for a board meeting evaluation.

Meeting summary:
{summary}

Write exactly 3 "Practitioner Celebrates" items and 3 "Practitioner Recommends" items.

ESB framework principles:
- Boards should spend >50% of public meeting time on Goal Setting + Goal Monitoring
- Board Work = adopted Student Outcome Goals + Guardrails + legally required items
- Student outcomes = what students know/can do at END of cycle (summative only)
- The board sets direction; the superintendent implements

Format: Each item has a heading (5-8 words) and a body paragraph (3-4 sentences).
Be specific to this meeting's actual content, not generic.
Celebrates should note genuine governance strengths observed.
Recommends should offer actionable ESB-aligned improvements.

Respond with JSON:
{{
  "celebrates": [{{"heading": "...", "body": "..."}}],
  "recommends": [{{"heading": "...", "body": "..."}}]
}}"""

    result = await _chat([{"role": "user", "content": prompt}], temperature=0.4)
    return json.loads(_strip_json_fence(result))


def compute_category_totals(classified: List[Dict], total_minutes: int) -> Dict[str, Any]:
    """Aggregate minutes by category and compute percentages."""
    totals: Dict[str, int] = {}
    goal_focused = 0

    for item in classified:
        cat = item["category"]
        mins = item.get("minutes", 0)
        totals[cat] = totals.get(cat, 0) + mins
        if item.get("goal_focused"):
            goal_focused += mins

    return {
        "by_category": totals,
        "goal_focused_minutes": goal_focused,
        "total_minutes": total_minutes,
        "goal_focused_pct": round(goal_focused / total_minutes * 100, 1) if total_minutes else 0,
    }


# ── Multi-Meeting Governance Review (schoolboardreview.com methodology) ────────

GOVERNANCE_CRITERIA = [
    {
        "key": "focus_mindset",
        "name": "Focus Mindset",
        "desc": "Board members anchor discussion in student-outcome language and redirect operational tangents back to measurable impact on learners.",
    },
    {
        "key": "clarify_priorities",
        "name": "Clarify Priorities",
        "desc": "Board references adopted strategic priorities during deliberation and declines work lacking a clear line to those priorities.",
    },
    {
        "key": "monitor_progress",
        "name": "Monitor Progress",
        "desc": "Board systematically follows up on data, performance indicators, and prior monitoring flags with a structured monitoring calendar.",
    },
    {
        "key": "align_resources",
        "name": "Align Resources",
        "desc": "Budget and resource decisions are explicitly tied to strategic priorities rather than approved without strategy-alignment statements.",
    },
    {
        "key": "communicate_results",
        "name": "Communicate Results",
        "desc": "Board makes student-outcome results publicly legible in accessible formats, not buried in staff presentations.",
    },
]


async def score_meeting_governance(transcript: str, district: str, meeting_date: str) -> Dict[str, Any]:
    """Score one meeting on the 5 schoolboardreview.com governance criteria (20 pts each)."""
    criteria_list = "\n".join(
        f"- {c['name']}: {c['desc']}" for c in GOVERNANCE_CRITERIA
    )
    prompt = f"""You are a school board governance expert scoring a board meeting transcript.

District: {district}
Meeting date: {meeting_date}

Score this meeting on each of the following 5 criteria, 0-20 points each (100 total).
Be rigorous — a score of 20 means exceptional, consistent evidence; 10 means average; 0 means no evidence at all.

CRITERIA:
{criteria_list}

TRANSCRIPT (first 12,000 chars):
{transcript[:12000]}

For each criterion provide:
- score: integer 0-20
- notes: 2-3 sentences citing specific evidence from the transcript
- examples: one direct example quote or observation (keep brief)

Respond with JSON only:
{{
  "meeting_date": "{meeting_date}",
  "focus_mindset": {{"score": 0, "notes": "...", "examples": "..."}},
  "clarify_priorities": {{"score": 0, "notes": "...", "examples": "..."}},
  "monitor_progress": {{"score": 0, "notes": "...", "examples": "..."}},
  "align_resources": {{"score": 0, "notes": "...", "examples": "..."}},
  "communicate_results": {{"score": 0, "notes": "...", "examples": "..."}}
}}"""

    result = await _chat([{"role": "user", "content": prompt}], temperature=0.2)
    data = json.loads(_strip_json_fence(result))
    data["composite"] = sum(data[c["key"]]["score"] for c in GOVERNANCE_CRITERIA)
    data["meeting_date"] = meeting_date
    return data


async def find_district_meetings(
    district: str, hint_url: str, months: int, max_meetings: int,
    anchor_date: str = None,
) -> List[Dict[str, str]]:
    """Use Perplexity to find public board meeting video URLs for a district within the past N months.

    anchor_date: the date of the submitted meeting (YYYY-MM-DD). The search window ends on
    this date, not today — so "3-month review" means the 3 months ending with this meeting,
    not the 3 months ending with today.
    """
    import datetime
    if anchor_date:
        try:
            end = datetime.date.fromisoformat(anchor_date)
        except ValueError:
            end = datetime.date.today()
    else:
        end = datetime.date.today()
    start = end - datetime.timedelta(days=months * 30)

    prompt = f"""Find public school board meeting VIDEO recordings for {district} from {start.isoformat()} to {end.isoformat()}.

Search their official meeting portal (Granicus, Swagit, YouTube, or similar). Return up to {max_meetings} meetings, newest first.

Hint URL (may help identify their video platform): {hint_url}

Return ONLY a JSON array, no other text:
[{{"url": "https://...", "date": "YYYY-MM-DD", "title": "Regular Board Meeting"}}]

If you cannot find specific URLs, return an empty array: []"""

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": "https://gotb.effectiveschoolboards.com",
        "X-Title": "ESB Portal",
    }
    payload = {
        "model": "perplexity/sonar-pro",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 2048,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(OPENROUTER_URL, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    raw = _strip_json_fence(data["choices"][0]["message"]["content"])
    try:
        meetings = json.loads(raw)
        return [m for m in meetings if m.get("url")][:max_meetings]
    except Exception:
        return []


def aggregate_multi_meeting_scores(scored_meetings: List[Dict]) -> Dict[str, Any]:
    """Average scores across meetings and compute trend for each criterion."""
    if not scored_meetings:
        return {}

    agg: Dict[str, Any] = {}
    for c in GOVERNANCE_CRITERIA:
        key = c["key"]
        scores = [m[key]["score"] for m in scored_meetings if key in m]
        if not scores:
            continue
        avg = sum(scores) / len(scores)
        mid = len(scores) // 2
        if mid > 0:
            early_avg = sum(scores[:mid]) / mid
            late_avg = sum(scores[mid:]) / (len(scores) - mid)
            if late_avg - early_avg > 1.5:
                trend = "Improving"
            elif early_avg - late_avg > 1.5:
                trend = "Declining"
            else:
                trend = "Stable"
        else:
            trend = "—"
        agg[key] = {"avg": round(avg, 1), "trend": trend, "scores": scores}

    composites = [m["composite"] for m in scored_meetings if "composite" in m]
    agg["composite_avg"] = round(sum(composites) / len(composites), 1) if composites else 0
    return agg


async def generate_multi_meeting_reflections(
    scored_meetings: List[Dict],
    aggregate: Dict[str, Any],
    district: str,
    span_label: str,
) -> Dict[str, List[Dict]]:
    """Generate coaching celebrates and recommends for a multi-meeting review."""
    summary_lines = [f"District: {district}", f"Review span: {span_label}", f"Meetings analyzed: {len(scored_meetings)}", ""]
    summary_lines.append(f"Composite avg: {aggregate.get('composite_avg', 0):.1f} / 100")
    for c in GOVERNANCE_CRITERIA:
        key = c["key"]
        if key in aggregate:
            info = aggregate[key]
            summary_lines.append(f"  {c['name']}: avg {info['avg']:.1f}/20 — trend {info['trend']}")

    prompt = f"""You are AJ Crabill, an ESB (Effective School Boards) Certified Great on Their Behalf Practitioner writing a governance review for a board client.

You have analyzed {len(scored_meetings)} board meeting(s) covering {span_label}.

Summary:
{chr(10).join(summary_lines)}

Meeting-by-meeting composites:
{chr(10).join(f"  {m.get('meeting_date','?')}: {m.get('composite',0)}/100" for m in scored_meetings)}

Write exactly 3 "Practitioner Celebrates" items and 3 "Practitioner Recommends" items.
- Celebrates: genuine governance strengths observed consistently across the period
- Recommends: specific, actionable ESB-aligned improvements tied to patterns you saw
- Be specific to trends across the period, not generic advice
- Each item has a heading (5-8 words) and a body paragraph (3-4 sentences)

ESB framework: boards should spend >50% of public time on Goal Setting + Goal Monitoring.
Board Work = adopted Student Outcome Goals + Guardrails + legally required items.

Respond with JSON:
{{
  "celebrates": [{{"heading": "...", "body": "..."}}],
  "recommends": [{{"heading": "...", "body": "..."}}]
}}"""

    result = await _chat([{"role": "user", "content": prompt}], temperature=0.4)
    return json.loads(_strip_json_fence(result))
