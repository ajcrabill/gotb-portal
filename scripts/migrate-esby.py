"""
Migration: esby.effectiveschoolboards.com backend (:8443) → esb-portal

Source of truth for esby: board meeting evaluations.
Per architecture §4 / IV-1: esby :8443 is authoritative for this entity type.

Run FIRST (before migrate-gotb.py). Outputs a merge map so gotb migration can dedup.

Usage:
    python scripts/migrate-esby.py \
        --esby-db postgresql://... \
        --portal-db postgresql://... \
        --dry-run
"""
import argparse
import sys

# TODO Phase 0 implementation:
# 1. Connect to source esby DB and portal DB
# 2. For each Person in esby:
#    a. Lookup by email in portal DB
#    b. Create if not found; record old-PK → unified-PK in merge map
# 3. Migrate BoardMeetingEvaluations with scoring_config_version="legacy@<hash>"
# 4. Migrate any RoleMemberships
# 5. Output merge map JSON for gotb migration cross-reference
# 6. PK collisions beyond email-match go to manual merge review queue

parser = argparse.ArgumentParser(description="Migrate esby backend to esb-portal")
parser.add_argument("--esby-db", required=True)
parser.add_argument("--portal-db", required=True)
parser.add_argument("--dry-run", action="store_true")
parser.add_argument("--output", default="scripts/output/esby-merge-map.json")

if __name__ == "__main__":
    args = parser.parse_args()
    print(f"[esby-migrate] dry_run={args.dry_run}")
    print("[esby-migrate] TODO: implement in Phase 0")
    sys.exit(0)
