#!/usr/bin/env python3
"""Refuse a change to the published skills that leaves the marketplace version untouched.

Usage: check-version-bump.py <base-ref>      (e.g. origin/main)

Rules enforced:
  - when the diff from the merge base with <base-ref> to the working tree touches skills/,
    scripts/ or .claude-plugin/marketplace.json, metadata.version in the working tree must be
    a semver triple strictly greater than the one at <base-ref>
  - other changes (docs, workflows) need no bump
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

MANIFEST = ".claude-plugin/marketplace.json"
WATCHED = ("skills/", "scripts/", MANIFEST)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def semver(raw: str, where: str) -> tuple[int, ...]:
    parts = raw.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        print(f"::error::metadata.version '{raw}' at {where} is not a semver triple")
        sys.exit(1)
    return tuple(int(p) for p in parts)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    base = sys.argv[1]
    changed = git("diff", "--name-only", git("merge-base", base, "HEAD").strip()).split()
    if not any(f.startswith(WATCHED) for f in changed):
        print("no change under skills/, scripts/ or the marketplace manifest; no bump required")
        return 0
    old = semver(json.loads(git("show", f"{base}:{MANIFEST}"))["metadata"]["version"], base)
    new = semver(json.loads(Path(MANIFEST).read_text())["metadata"]["version"], "HEAD")
    dotted = ".".join
    if new <= old:
        print(f"::error::bump metadata.version in {MANIFEST} (base {dotted(map(str, old))}, head {dotted(map(str, new))})")
        return 1
    print(f"metadata.version bumped {dotted(map(str, old))} -> {dotted(map(str, new))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
