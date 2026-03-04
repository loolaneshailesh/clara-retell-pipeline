import argparse
import json
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

# Add scripts directory to path so we can import sibling modules
sys.path.insert(0, os.path.dirname(__file__))

from transcript_normalizer import normalize_text
from extract_account_memo import build_memo as build_memo_from_text


# ---------------------------------------------------------------------------
# Deep diff helpers
# ---------------------------------------------------------------------------

def _flatten(obj: Any, prefix: str = "", sep: str = ".") -> Dict[str, Any]:
    """Flatten a nested dict/list into dot-notation key -> value pairs."""
    items: Dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{prefix}{sep}{k}" if prefix else k
            items.update(_flatten(v, new_key, sep))
    elif isinstance(obj, list):
        # treat lists as atomic values for diff
        items[prefix] = obj
    else:
        items[prefix] = obj
    return items


def compute_diff(
    old: Dict[str, Any],
    new: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Return list of {field, old_value, new_value, reason} for changed fields."""
    old_flat = _flatten(old)
    new_flat = _flatten(new)

    changes: List[Dict[str, Any]] = []
    all_keys = set(old_flat.keys()) | set(new_flat.keys())

    for key in sorted(all_keys):
        old_val = old_flat.get(key)
        new_val = new_flat.get(key)
        if old_val != new_val:
            # Only record if the new value is non-null / non-empty and different
            if new_val not in (None, "", [], {}):
                changes.append({
                    "field": key,
                    "old_value": old_val,
                    "new_value": new_val,
                    "reason": "Updated based on onboarding call transcript."
                })
    return changes


# ---------------------------------------------------------------------------
# Patch application
# ---------------------------------------------------------------------------

def _set_nested(obj: Dict[str, Any], dot_path: str, value: Any) -> None:
    """Set a value in a nested dict using a dot-notation path.
    Silently skips if intermediate keys don't exist or path includes list indices.
    """
    parts = dot_path.split(".")
    cur = obj
    for part in parts[:-1]:
        if not isinstance(cur, dict) or part not in cur:
            return  # can't traverse - skip
        cur = cur[part]
    last = parts[-1]
    if isinstance(cur, dict):
        cur[last] = value


def apply_patch(
    base: Dict[str, Any],
    changes: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Apply a list of change records to a base memo, returning updated copy."""
    updated = deepcopy(base)
    for change in changes:
        _set_nested(updated, change["field"], change["new_value"])
    return updated


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Apply onboarding transcript data to v1 memo, producing v2 memo + changelog."
    )
    parser.add_argument("--base-memo", required=True, help="Path to v1 memo.json")
    parser.add_argument("--onboarding", required=True, help="Path to raw onboarding transcript")
    parser.add_argument("--out-memo", required=True, help="Path to write v2 memo.json")
    parser.add_argument("--changelog", required=True, help="Path to write changelog JSON")
    parser.add_argument("--account-id", required=True, help="Account identifier")
    args = parser.parse_args()

    # 1. Load base memo (v1)
    with open(args.base_memo, "r", encoding="utf-8") as f:
        base_memo: Dict[str, Any] = json.load(f)

    # 2. Normalize and extract from onboarding transcript
    with open(args.onboarding, "r", encoding="utf-8") as f:
        raw_onboarding = f.read()

    normalized = normalize_text(raw_onboarding)
    onboarding_memo = build_memo_from_text(normalized, args.account_id)

    # 3. Compute diff between base and onboarding-derived memo
    changes = compute_diff(base_memo, onboarding_memo)

    # 4. Apply patch to produce v2 memo
    v2_memo = apply_patch(base_memo, changes)

    # 5. Write v2 memo
    os.makedirs(os.path.dirname(args.out_memo), exist_ok=True)
    with open(args.out_memo, "w", encoding="utf-8") as f:
        json.dump(v2_memo, f, indent=2)
    print(f"[patch] v2 memo written: {args.out_memo}")

    # 6. Write changelog
    changelog = {
        "account_id": args.account_id,
        "from_version": "v1",
        "to_version": "v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_changes": len(changes),
        "changes": changes
    }
    os.makedirs(os.path.dirname(args.changelog), exist_ok=True)
    with open(args.changelog, "w", encoding="utf-8") as f:
        json.dump(changelog, f, indent=2)
    print(f"[patch] Changelog written: {args.changelog} ({len(changes)} changes)")


if __name__ == "__main__":
    main()
