"""
Migration: gotb.effectiveschoolboards.com backend (:10000) → esb-portal

Source of truth for gotb: users, districts, assessment sessions, assessment submissions.
Per architecture §4 / IV-1: gotb :10000 is authoritative for these entity types.

Run after migrate-esby.py; cross-references the esby migration output for Person dedup.

Usage:
    python scripts/migrate-gotb.py \
        --gotb-db postgresql://... \
        --portal-db postgresql://... \
        --esby-merge-map scripts/output/esby-merge-map.json \
        --dry-run
"""
import argparse
import json
import sys

# TODO Phase 0 implementation:
# 1. Connect to source GOTB DB and portal DB
# 2. For each Person in GOTB:
#    a. Lookup by email in portal DB
#    b. If found (from esby migration): merge, record old-PK → unified-PK in merge map
#    c. If not found: create new Person, record in merge map
# 3. Migrate Districts from Devon CRM (already in GOTB DB)
#    - Flag CGCS members (cross-reference known CGCS list)
#    - Set is_cgcs_member=True, log flagged count
# 4. Migrate AssessmentSessions with scoring_config_version="legacy@<hash>"
#    - All legacy rows must have a version stamp (no unversioned rows)
# 5. Migrate RoleMemberships
# 6. Output merge map JSON for cross-reference
# 7. --dry-run: print counts only, no writes

parser = argparse.ArgumentParser(description="Migrate GOTB backend to esb-portal")
parser.add_argument("--gotb-db", required=True)
parser.add_argument("--portal-db", required=True)
parser.add_argument("--esby-merge-map", required=True)
parser.add_argument("--dry-run", action="store_true")
parser.add_argument("--output", default="scripts/output/gotb-merge-map.json")

if __name__ == "__main__":
    args = parser.parse_args()
    print(f"[gotb-migrate] dry_run={args.dry_run}")
    print("[gotb-migrate] TODO: implement in Phase 0")
    sys.exit(0)
