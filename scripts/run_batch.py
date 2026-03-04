"""run_batch.py

Batch runner: processes all accounts in dataset/demo/ and dataset/onboarding/
without needing n8n. Useful for local testing.

Usage:
    # Run Pipeline A for all demo transcripts:
    python run_batch.py --pipeline a

    # Run Pipeline B for all onboarding transcripts (requires v1 already generated):
    python run_batch.py --pipeline b

    # Run both in sequence:
    python run_batch.py --pipeline all

Paths are relative to the project root (one level above scripts/).
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).parent.parent


def run_cmd(cmd: list, cwd: Path = None) -> bool:
    """Run a command, print output, return True if success."""
    cmd_str = " ".join(str(c) for c in cmd)
    print(f"\n>>> {cmd_str}")
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True)
    if result.returncode != 0:
        print(f"[FAILED] Exit code: {result.returncode}")
        return False
    return True


def get_account_ids(dataset_dir: Path) -> list:
    """Return list of account IDs from .txt files in the given directory."""
    if not dataset_dir.exists():
        print(f"[WARNING] Dataset directory not found: {dataset_dir}")
        return []
    return [f.stem for f in sorted(dataset_dir.glob("*.txt"))]


def run_pipeline_a(account_id: str, root: Path):
    scripts = root / "scripts"
    demo_path = root / "dataset" / "demo" / f"{account_id}.txt"
    tmp_normalized = root / "outputs" / "tmp" / f"{account_id}_demo_normalized.txt"
    memo_path = root / "outputs" / "accounts" / account_id / "v1" / "memo.json"
    spec_path = root / "outputs" / "accounts" / account_id / "v1" / "agent_spec.json"
    prompt_template = root / "config" / "prompt_templates" / "base_system_prompt.txt"

    print(f"\n{'='*60}")
    print(f"[Pipeline A] Account: {account_id}")
    print(f"{'='*60}")

    ok = run_cmd([
        sys.executable,
        str(scripts / "transcript_normalizer.py"),
        "--input", str(demo_path),
        "--output", str(tmp_normalized)
    ])
    if not ok:
        return False

    ok = run_cmd([
        sys.executable,
        str(scripts / "extract_account_memo.py"),
        "--input", str(tmp_normalized),
        "--output", str(memo_path),
        "--account-id", account_id
    ])
    if not ok:
        return False

    ok = run_cmd([
        sys.executable,
        str(scripts / "generate_retell_spec.py"),
        "--memo", str(memo_path),
        "--version", "v1",
        "--output", str(spec_path),
        "--prompt-template", str(prompt_template)
    ])
    return ok


def run_pipeline_b(account_id: str, root: Path):
    scripts = root / "scripts"
    onboarding_path = root / "dataset" / "onboarding" / f"{account_id}.txt"
    tmp_normalized = root / "outputs" / "tmp" / f"{account_id}_onboarding_normalized.txt"
    base_memo = root / "outputs" / "accounts" / account_id / "v1" / "memo.json"
    v2_memo = root / "outputs" / "accounts" / account_id / "v2" / "memo.json"
    v2_spec = root / "outputs" / "accounts" / account_id / "v2" / "agent_spec.json"
    changelog = root / "changelog" / f"{account_id}.changes.json"
    prompt_template = root / "config" / "prompt_templates" / "base_system_prompt.txt"

    print(f"\n{'='*60}")
    print(f"[Pipeline B] Account: {account_id}")
    print(f"{'='*60}")

    if not base_memo.exists():
        print(f"[ERROR] v1 memo not found for {account_id}. Run Pipeline A first.")
        return False

    ok = run_cmd([
        sys.executable,
        str(scripts / "apply_onboarding_patch.py"),
        "--base-memo", str(base_memo),
        "--onboarding", str(onboarding_path),
        "--out-memo", str(v2_memo),
        "--changelog", str(changelog),
        "--account-id", account_id
    ])
    if not ok:
        return False

    ok = run_cmd([
        sys.executable,
        str(scripts / "generate_retell_spec.py"),
        "--memo", str(v2_memo),
        "--version", "v2",
        "--output", str(v2_spec),
        "--prompt-template", str(prompt_template)
    ])
    return ok


def main():
    parser = argparse.ArgumentParser(
        description="Batch runner for clara-retell-pipeline."
    )
    parser.add_argument(
        "--pipeline",
        choices=["a", "b", "all"],
        default="all",
        help="Which pipeline to run: a (demo->v1), b (onboarding->v2), or all"
    )
    parser.add_argument(
        "--account-id",
        help="Process only this account ID (optional; default: all accounts in dataset)"
    )
    args = parser.parse_args()

    root = get_project_root()
    print(f"[batch] Project root: {root}")

    # Ensure output dirs exist
    (root / "outputs" / "tmp").mkdir(parents=True, exist_ok=True)
    (root / "changelog").mkdir(parents=True, exist_ok=True)

    results = {"success": [], "failed": []}

    if args.pipeline in ("a", "all"):
        demo_dir = root / "dataset" / "demo"
        if args.account_id:
            account_ids = [args.account_id]
        else:
            account_ids = get_account_ids(demo_dir)

        print(f"\n[batch] Pipeline A: {len(account_ids)} accounts")
        for aid in account_ids:
            ok = run_pipeline_a(aid, root)
            (results["success"] if ok else results["failed"]).append(f"A:{aid}")

    if args.pipeline in ("b", "all"):
        onboarding_dir = root / "dataset" / "onboarding"
        if args.account_id:
            account_ids = [args.account_id]
        else:
            account_ids = get_account_ids(onboarding_dir)

        print(f"\n[batch] Pipeline B: {len(account_ids)} accounts")
        for aid in account_ids:
            ok = run_pipeline_b(aid, root)
            (results["success"] if ok else results["failed"]).append(f"B:{aid}")

    print(f"\n{'='*60}")
    print(f"[batch] SUMMARY")
    print(f"  Succeeded: {len(results['success'])}")
    print(f"  Failed:    {len(results['failed'])}")
    if results["failed"]:
        print(f"  Failed items: {results['failed']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
