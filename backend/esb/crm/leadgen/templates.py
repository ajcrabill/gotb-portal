"""AJ's 10-touch outreach cadence. Templates are FIXED (his words); the composer
only fills the {bracketed} variables and picks the document. Touch 1 subject is
"Effective School Board"; 2+ are "Re: …" (same thread). Intervals are days after
the PREVIOUS touch.

Variables filled per sequence (extracted once from dossier/signal):
  first_name, district_name, trigger_context, scope_detail, document,
  alt_document, governance_challenge, trigger_brief, governance_topic
Empty optional variables collapse cleanly.
"""
from __future__ import annotations

SIGNATURE = "AJ Crabill, Senior Coach\nEffective School Boards"  # marker in template bodies

# Light on cold touches (best deliverability), full promo block once engaged (touch 3+).
TAGLINE = "Student outcomes don't change until adult behaviors change.™"
NAME_BLOCK = "AJ Crabill, Senior Coach\nEffective School Boards"  # = SIGNATURE marker
SIGNATURE_LIGHT = f"{NAME_BLOCK}\n\n\n\n{TAGLINE}"
SIGNATURE_FULL = (
    f"{NAME_BLOCK}\n\n"
    "My new book is out — get a copy, read the intro, or watch the video: "
    "http://www.studentledrp.org/book/\n"
    "The 3rd edition of my book about school boards is now available: "
    "http://www.effectiveschoolboards.com/publications/\n"
    "Subscribe to The Effective School Board Member newsletter: "
    "http://www.effectiveschoolboards.com/newsletter/\n\n\n\n"
    f"{TAGLINE}"
)


def signature_for(touch_n: int) -> str:
    return SIGNATURE_LIGHT if touch_n <= 2 else SIGNATURE_FULL

TOUCHES: list[dict] = [
    {
        "n": 1, "name": "Initial Outreach", "interval_days": 0,
        "subject": "Effective School Board",
        "body": (
            "Hi {first_name},\n\n"
            "May I send you our free guidance document on {document}?\n\n"
            "{why_sentence}\n\n"
            "My team of certified school board coaches specializes in helping "
            "leadership teams focus on student outcomes. As this work continues, "
            "would it be useful if I shared the document with you?\n\n" + SIGNATURE
        ),
    },
    {
        "n": 2, "name": "Follow-up Nudge", "interval_days": 7,
        "subject": "Re: Effective School Board",
        "body": (
            "Hi {first_name},\n\n"
            "Following up on my earlier note — wanted to make sure you saw it. "
            "Happy to send our free guidance document on {document} if timing is "
            "better now.\n\n" + SIGNATURE
        ),
    },
    {
        "n": 3, "name": "Different Angle", "interval_days": 7,
        "subject": "Re: Effective School Board",
        "body": (
            "Hi {first_name},\n\n"
            "Hope all is well. Wanted to share another resource that might be useful "
            "for your board — our guidance document on {alt_document}.\n\n"
            "Would this be helpful?\n\n" + SIGNATURE
        ),
    },
    {
        "n": 4, "name": "Value-Add Insight", "interval_days": 7,
        "subject": "Re: Effective School Board",
        "body": (
            "Hi {first_name},\n\n"
            "Quick thought: one thing I've seen make a real difference for boards "
            "navigating {governance_challenge} is having a clear framework for how "
            "they approach it. Our guidance document on {document} walks through "
            "exactly how to do that.\n\n"
            "Happy to send it if useful.\n\n" + SIGNATURE
        ),
    },
    {
        "n": 5, "name": "Social Proof", "interval_days": 14,
        "subject": "Re: Effective School Board",
        "body": (
            "Hi {first_name},\n\n"
            "Just circling back. Our coaching team works with school boards across "
            "the country on exactly the kinds of challenges {district_name} is "
            "navigating — {trigger_brief}.\n\n"
            "Would it be useful to see our guidance document on {document}?\n\n" + SIGNATURE
        ),
    },
    {
        "n": 6, "name": "Direct Ask", "interval_days": 14,
        "subject": "Re: Effective School Board",
        "body": (
            "Hi {first_name},\n\n"
            "I'll be direct: can I send you our guide on {document}? No strings, "
            "no follow-up unless you want one.\n\n"
            "Interested?\n\n" + SIGNATURE
        ),
    },
    {
        "n": 7, "name": "Break-up", "interval_days": 21,
        "subject": "Re: Effective School Board",
        "body": (
            "Hi {first_name},\n\n"
            "This is my last note on this — unless you're interested, we'll stop here.\n\n"
            "If you ever want to explore how focused school board coaching could "
            "support {district_name}'s work, reply anytime. No pressure.\n\n"
            "Wishing you and your board a productive year.\n\n" + SIGNATURE
        ),
    },
    {
        "n": 8, "name": "Quarterly Re-engagement 1", "interval_days": 90,
        "subject": "Re: Effective School Board",
        "body": (
            "Hi {first_name},\n\n"
            "Hope things are going well. Wanted to check back in — if the timing is "
            "better now, I'd still be happy to share our guidance document on "
            "{document}.\n\nNo pressure either way.\n\n" + SIGNATURE
        ),
    },
    {
        "n": 9, "name": "Quarterly Re-engagement 2", "interval_days": 90,
        "subject": "Re: Effective School Board",
        "body": (
            "Hi {first_name},\n\n"
            "Circling back one more time. If the board is focusing on "
            "{governance_topic}, our team has resources that might help.\n\n"
            "Happy to send our guide on {document} if useful.\n\n" + SIGNATURE
        ),
    },
    {
        "n": 10, "name": "Quarterly Re-engagement 3", "interval_days": 90,
        "subject": "Re: Effective School Board",
        "body": (
            "Hi {first_name},\n\n"
            "Last check-in on this from me. If your board ever wants to explore how "
            "focused coaching could support your governance work, the door is open.\n\n"
            "Wishing you and your board all the best.\n\n" + SIGNATURE
        ),
    },
]

TOUCH_BY_N = {t["n"]: t for t in TOUCHES}
MAX_TOUCH = 10

# Default guidance docs; alternates only when confidence >= 0.95 on a better fit.
DEFAULT_DOCS = ("Effective Strategic Planning", "Effective Goal Monitoring")

# The real ESB guidance library (19 docs) + when each fits. The doc-selection seam
# picks from THIS, defaulting to Strategic Planning / Goal Monitoring when nothing
# specific applies. (Drive folder 12wa9OiZwHEy8gjH8VCuwUMitqqGhLTM7.)
DOCUMENT_CATALOG = [
    ("Effective Strategic Planning", "starting or refreshing a strategic plan / setting long-term direction"),
    ("Effective Goal Monitoring", "reviewing data and progress on goals; accountability for student outcomes (default for active boards)"),
    ("Effective Goal & Guardrail Setting", "setting goals and guardrails — defining what the board wants and won't accept"),
    ("Effective Agenda Design", "meetings run long or unfocused; agenda/meeting structure"),
    ("Completing A Board Time Use Evaluation", "the board spends too much time on operations instead of student outcomes"),
    ("Effective Budget Alignment", "budget season; aligning the budget to student-outcome priorities"),
    ("Effective Conflict Navigation", "board conflict, split votes, dysfunction, or interpersonal tension"),
    ("Effective Governance Crisis Communications", "a scandal, investigation, negative press, or public crisis"),
    ("Effective Policy Leadership", "policy overhaul or policy-committee work"),
    ("Effective Professional Services Management", "selecting or managing vendors — legal counsel, auditors, search firms"),
    ("Effective Research Analysis", "the board is leaning on data and research to make decisions"),
    ("Effective Risk Management", "safety, financial, legal, or reputational risk events"),
    ("Effective School Board Member Onboarding", "newly elected or appointed members joining the board"),
    ("Effective School Boards 101", "a board new to outcomes-focused governance, or no specific trigger — a primer"),
    ("Effective Student Voice in Governance", "student engagement, student board members, elevating student voice"),
    ("Ideas About Right-Sizing", "declining enrollment, school closures, consolidation, or right-sizing"),
    ("Inclusive Decision Making", "equity and inclusion initiatives; broadening who is at the table"),
    ("Superintendent Search Process", "an open superintendent position or active search"),
    ("Superintendent Transition Process", "a superintendent departure or an incoming superintendent transition"),
]

# Sequence advances ONLY from these statuses; anything else terminates it.
LIVE_STATUSES = {"not_contacted", "email_sent"}
