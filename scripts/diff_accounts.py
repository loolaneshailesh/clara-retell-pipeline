"""diff_accounts.py

CLI utility to compare two memo.json files (e.g. v1 vs v2)
and print a human-readable diff to stdout.

Usage:
    python diff_accounts.py --v1 outputs/accounts/acme_fire_001/v1/memo.json \\
                            --v2 outputs/accounts/acme_fire_001/v2/memo.json
"""
import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from apply_onboarding_patch import compute_diff


def main():
    parser = argparse.ArgumentParser(
        description="Compare two memo JSON files and print the diff."
    )
    parser.add_argument("--v1", required=True, help="Path to v1 memo.json")
    parser.add_argument("--v2", required=True, help="Path to v2 memo.json")
    parser.add_argument("--json", action="store_true", help="Output diff as JSON")
    args = parser.parse_args()

    with open(args.v1, "r", encoding="utf-8") as f:
        v1 = json.load(f)
    with open(args.v2, "r", encoding="utf-8") as f:
        v2 = json.load(f)

    changes = compute_diff(v1, v2)

    if args.json:
        print(json.dumps(changes, indent=2))
        return

    if not changes:
        print("No differences found between v1 and v2.")
        return

    print(f"Found {len(changes)} difference(s) between v1 and v2:\n")
    for i, c in enumerate(changes, 1):
        print(f"  [{i}] Field: {c['field']}")
        print(f"       Old: {json.dumps(c['old_value'], ensure_ascii=False)}")
        print(f"       New: {json.dumps(c['new_value'], ensure_ascii=False)}")
        print(f"       Reason: {c['reason']}")
        print()


if __name__ == "__main__":
    main()
