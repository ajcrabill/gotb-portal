# Content pipeline (Sys-1)
#
# Two stages, both required for ESB-generated content:
#   Stage 1 — deterministic floor (antislop.py)
#       Port of /home/libra/coach-libra/coach_libra/edit/antislop.py
#       Tiered banned vocab (TIER1/TIER2/TIER3), structural tics, cleanliness score 0-100
#       Context-aware: allow-list for sanctioned phrases, "Coach" fail bound to
#       client-facing-audience flag, warn vs. fail tiers, regression fixtures
#
#   Stage 2 — independent-model LLM reviewer (quality.py)
#       Port of /home/libra/coach-libra/coach_libra/watch/quality.py
#       Runs on DIFFERENT model than any writer (independence rule, Sys-11)
#       Conservative: block only on confident serious problems
#       Re-renders once, then holds + escalates to CM hold queue
#
# Degraded mode (Sys-1):
#   - Hard fail-CLOSED: IP/legal/validation strings
#   - Fail-OPEN-with-flag: low-risk strings (recorded as stage2_skipped_unavailable)
#   - Circuit breaker + fallback model + content-addressed verdict cache
#
# Author-time vs render-time:
#   - Templates/questions/disclaimers/guidance: Stage-2 runs ONCE at author-time, verdict cached
#   - Dynamic slots interpolated into pre-cleared templates: Stage-1 only at render-time
#   - Error/empty-state/button strings: author-time literals, never a synchronous LLM call
