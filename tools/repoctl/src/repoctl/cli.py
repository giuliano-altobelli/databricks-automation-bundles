from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from repoctl.changes import classify_changed_files
from repoctl.discovery import discover
from repoctl.evidence import check_evidence_files
from repoctl.validation import validate_repo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repoctl")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("discover", help="Discover projects and bundles")
    subparsers.add_parser("validate", help="Validate project and bundle metadata")

    changed_parser = subparsers.add_parser("changed", help="Classify changed files")
    changed_parser.add_argument("--base", required=True, help="Git ref to diff against")

    evidence_parser = subparsers.add_parser("evidence", help="Check promotion evidence")
    evidence_subparsers = evidence_parser.add_subparsers(
        dest="evidence_command", required=True
    )
    evidence_check_parser = evidence_subparsers.add_parser(
        "check", help="Check required evidence files"
    )
    evidence_check_parser.add_argument("--bundle", type=Path, required=True)
    evidence_check_parser.add_argument("--target", required=True)
    evidence_check_parser.add_argument("--evidence", type=Path, required=True)

    args = parser.parse_args(argv)
    root = args.root.resolve()

    if args.command == "discover":
        print(json.dumps(discover(root).to_json(root), indent=2, sort_keys=True))
        return 0

    if args.command == "validate":
        result = validate_repo(root)
        if result.ok:
            print("Validation ok")
            return 0
        print("Validation failed:", file=sys.stderr)
        for error in result.errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    if args.command == "changed":
        changed_files = _git_changed_files(root, args.base)
        result = classify_changed_files(root, changed_files)
        print(json.dumps(_changed_to_json(root, result), indent=2, sort_keys=True))
        return 0

    if args.command == "evidence":
        if args.evidence_command == "check":
            result = check_evidence_files(
                _resolve_input_path(root, args.bundle),
                args.target,
                _resolve_input_path(root, args.evidence),
            )
            if result.ok:
                print("Evidence ok")
                return 0
            print("Evidence check failed:", file=sys.stderr)
            for error in result.errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        parser.error(f"unsupported evidence command {args.evidence_command}")
        return 2

    parser.error(f"unsupported command {args.command}")
    return 2


def _resolve_input_path(root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def _git_changed_files(root: Path, base: str) -> list[str]:
    commands = [
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        ["git", "diff", "--name-only", "--cached"],
        ["git", "diff", "--name-only"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    changed_files: set[str] = set()
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        changed_files.update(line for line in completed.stdout.splitlines() if line.strip())
    return sorted(changed_files)


def _changed_to_json(root: Path, result: Any) -> dict[str, Any]:
    return {
        "changed_files": result.changed_files,
        "changed_bundles": [
            path.relative_to(root).as_posix() for path in result.changed_bundles
        ],
        "docs_only": result.docs_only,
        "affects_all_bundles": result.affects_all_bundles,
    }


if __name__ == "__main__":
    raise SystemExit(main())
