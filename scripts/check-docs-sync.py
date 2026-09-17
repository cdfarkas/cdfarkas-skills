#!/usr/bin/env python3
"""Refuse a change to a skill or to the tooling that leaves the Markdown docs untouched.

Usage: check-docs-sync.py [<base-ref>]      (e.g. origin/main; none = structural checks only)

Structural rules, always:
  - every skills/<name>/ carries README.md, SKILL.md and reference.md
  - the root README.md skills table has a row linking skills/<name>/
  - a skill with evals/RESULTS.md has a row in "Scores at a glance" and its README names evals/RESULTS.md
  - a skill with agents/ or hooks/ names them in its README

Diff rules, with <base-ref> (the diff from the merge base with <base-ref> to the working tree):
  - a change under skills/<name>/scripts/, hooks/, agents/ or to its SKILL.md also changes
    skills/<name>/README.md or reference.md
  - a change to scripts/*.py or .github/workflows/ci.yml also changes CLAUDE.md or
    docs/how-these-skills-are-built.md
  - a plugin added to or removed from .claude-plugin/marketplace.json also changes the root README.md
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

MANIFEST = ".claude-plugin/marketplace.json"
ROOT_README = Path("README.md")
TOOLING_DOCS = ("CLAUDE.md", "docs/how-these-skills-are-built.md")
CODE_DIRS = ("scripts/", "hooks/", "agents/")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def structural(skills: list[Path], readme: str) -> list[str]:
    errors: list[str] = []
    for skill in skills:
        name = skill.name
        for required in ("README.md", "SKILL.md", "reference.md"):
            if not (skill / required).is_file():
                errors.append(f"{skill}/{required} is missing")
        if f"](skills/{name}/)" not in readme:
            errors.append(f"root README table has no row linking skills/{name}/")
        skill_readme = (skill / "README.md").read_text() if (skill / "README.md").is_file() else ""
        if (skill / "evals/RESULTS.md").is_file():
            if not re.search(rf"^\| `{re.escape(name)}` \|.*RESULTS\.md", readme, re.M):
                errors.append(f"root README 'Scores at a glance' has no {name} row")
            if "evals/RESULTS.md" not in skill_readme:
                errors.append(f"{skill}/README.md does not mention evals/RESULTS.md")
        for folder in ("agents/", "hooks/"):
            if (skill / folder).is_dir() and folder not in skill_readme:
                errors.append(f"{skill}/README.md does not name {folder}")
    return errors


def plugin_names(raw: str) -> set[str]:
    return {p.get("name", "") for p in json.loads(raw).get("plugins", [])}


def diff_based(base: str, skills: list[Path]) -> list[str]:
    errors: list[str] = []
    changed = set(git("diff", "--name-only", git("merge-base", base, "HEAD").strip()).split())
    for skill in skills:
        prefix = f"{skill}/"
        code = any(f.startswith(prefix + d) for f in changed for d in CODE_DIRS) or prefix + "SKILL.md" in changed
        docs = prefix + "README.md" in changed or prefix + "reference.md" in changed
        if code and not docs:
            errors.append(f"{skill}: code changed, docs untouched (README.md / reference.md)")
    tooling = any(re.fullmatch(r"scripts/[^/]+\.py", f) for f in changed) or ".github/workflows/ci.yml" in changed
    if tooling and not any(d in changed for d in TOOLING_DOCS):
        errors.append(f"tooling changed, docs untouched ({' / '.join(TOOLING_DOCS)})")
    if MANIFEST in changed and Path(MANIFEST).is_file():
        before = plugin_names(git("show", f"{base}:{MANIFEST}"))
        after = plugin_names(Path(MANIFEST).read_text())
        if before != after and str(ROOT_README) not in changed:
            errors.append(f"plugins changed in {MANIFEST} ({', '.join(sorted(before ^ after))}), root README untouched")
    return errors


def main() -> int:
    if len(sys.argv) > 2:
        print(__doc__)
        return 2
    skills = sorted(p for p in Path("skills").iterdir() if p.is_dir())
    readme = ROOT_README.read_text() if ROOT_README.is_file() else ""
    errors = structural(skills, readme)
    if len(sys.argv) == 2:
        errors += diff_based(sys.argv[1], skills)
    for e in errors:
        print(f"::error::{e}")
    if errors:
        return 1
    print(f"docs follow the code: {len(skills)} skill(s) documented" + (" and the diff carries its docs" if len(sys.argv) == 2 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
