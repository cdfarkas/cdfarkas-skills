#!/usr/bin/env python3
"""Check every skills/*/evals/ folder without running any agent.

Rules enforced:
  - evals.json parses, `skill_name` equals the skill directory, `evals` has at least 3 cases,
    each with an `id`, a unique `name`, a non-empty `prompt` and a non-empty `assertions` list
  - grade.py imports and exposes a GRADERS dict keyed by exactly the case names of evals.json
  - each grader, called on an empty answer, returns as many assertions as evals.json lists
    for that case, every one with a non-empty text — the two files describe the same test
  - RESULTS.md exists and has, per case, a row `| `<name>` | N/M ...` where M is the case's
    assertion count and N <= M; `not measured` is accepted in the without-skill columns only;
    a missing row is a warning, not an error, when the file says the run is `not yet run`
  - a skill directory with no evals/evals.json is reported as a warning, never silently skipped
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.dont_write_bytecode = True

MIN_CASES = 3
NOT_RUN = "not yet run"
NOT_MEASURED = "not measured"
SCORE_RE = re.compile(r"^(\d+)/(\d+)\b")


def load_cases(path: Path, skill: str) -> tuple[list[dict], list[str]]:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        return [], [f"{path}: {exc}"]
    errors: list[str] = []
    if data.get("skill_name") != skill:
        errors.append(f"{path}: skill_name '{data.get('skill_name')}' must equal the directory '{skill}'")
    cases = data.get("evals")
    if not isinstance(cases, list) or len(cases) < MIN_CASES:
        errors.append(f"{path}: `evals` must list at least {MIN_CASES} cases")
        return [], errors
    seen: set[str] = set()
    for i, case in enumerate(cases):
        name = case.get("name")
        label = name or f"case #{i}"
        if "id" not in case:
            errors.append(f"{path}: {label} has no `id`")
        if not name:
            errors.append(f"{path}: {label} has no `name`")
        elif name in seen:
            errors.append(f"{path}: duplicate case name '{name}'")
        seen.add(name)
        if not case.get("prompt"):
            errors.append(f"{path}: {label} has an empty `prompt`")
        if not isinstance(case.get("assertions"), list) or not case["assertions"]:
            errors.append(f"{path}: {label} has no `assertions`")
    return cases, errors


def load_graders(path: Path) -> tuple[dict, list[str]]:
    try:
        spec = importlib.util.spec_from_file_location(f"grade_{path.parent.parent.name}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as exc:
        return {}, [f"{path}: does not import ({type(exc).__name__}: {exc})"]
    graders = getattr(module, "GRADERS", None)
    if not isinstance(graders, dict):
        return {}, [f"{path}: no GRADERS dict"]
    return graders, []


def check_graders(path: Path, graders: dict, cases: list[dict]) -> list[str]:
    errors: list[str] = []
    expected = {c["name"] for c in cases if c.get("name")}
    if set(graders) != expected:
        missing, extra = sorted(expected - set(graders)), sorted(set(graders) - expected)
        errors.append(f"{path}: GRADERS keys differ from evals.json (missing {missing}, extra {extra})")
    ctx = defaultdict(lambda: "X")
    for case in cases:
        name = case.get("name")
        if name not in graders:
            continue
        try:
            results = graders[name]("", ctx)
        except Exception as exc:
            errors.append(f"{path}: grader '{name}' raises on an empty answer ({type(exc).__name__}: {exc})")
            continue
        if len(results) != len(case["assertions"]):
            errors.append(f"{path}: grader '{name}' returns {len(results)} assertions, evals.json lists {len(case['assertions'])}")
        if any(not (isinstance(r, tuple) and r and r[0]) for r in results):
            errors.append(f"{path}: grader '{name}' has an assertion with an empty text")
    return errors


def check_results(path: Path, cases: list[dict]) -> tuple[list[str], list[str]]:
    if not path.exists():
        return [f"{path}: missing"], []
    text = path.read_text()
    errors: list[str] = []
    warnings: list[str] = []
    for case in cases:
        name, total = case.get("name"), len(case["assertions"])
        rows = [line for line in text.splitlines() if line.startswith(f"| `{name}` |")]
        if not rows:
            if NOT_RUN in text:
                warnings.append(f"{path}: no row for '{name}' (run {NOT_RUN})")
            else:
                errors.append(f"{path}: no row for '{name}'")
            continue
        cells = [c.strip() for c in rows[0].strip("|").split("|")][1:]
        for i, cell in enumerate(cells):
            m = SCORE_RE.match(cell)
            if m is None:
                if i == 0 or cell != NOT_MEASURED:
                    errors.append(f"{path}: '{name}' column {i + 1} is '{cell}', expected N/{total}")
                continue
            n, m_total = int(m.group(1)), int(m.group(2))
            if m_total != total or n > total:
                errors.append(f"{path}: '{name}' scores {cell}, evals.json lists {total} assertions")
    return errors, warnings


def check(evals_dir: Path) -> tuple[list[str], list[str]]:
    skill = evals_dir.parent.name
    cases, errors = load_cases(evals_dir / "evals.json", skill)
    if not cases:
        return errors, []
    graders, grader_errors = load_graders(evals_dir / "grade.py")
    errors += grader_errors
    if graders:
        errors += check_graders(evals_dir / "grade.py", graders, cases)
    result_errors, warnings = check_results(evals_dir / "RESULTS.md", cases)
    return errors + result_errors, warnings


def main() -> int:
    skills = sorted(p for p in Path("skills").glob("*/") if p.is_dir())
    if not skills:
        print("no skills found under skills/")
        return 1

    all_errors, all_warnings, dirs = [], [], []
    for skill in skills:
        d = skill / "evals"
        if not (d / "evals.json").exists():
            all_warnings.append(f"{skill.as_posix()}: no evals/ yet")
            continue
        dirs.append(d)
        errors, warnings = check(d)
        all_errors += errors
        all_warnings += warnings

    for w in all_warnings:
        print(f"  warn {w}")
    if all_errors:
        print(f"Found {len(all_errors)} problem(s):\n")
        for e in all_errors:
            print(f"  ✗ {e}")
        return 1

    print(f"✓ {len(dirs)} skill(s) evaluated consistently "
          f"(evals.json, grade.py and RESULTS.md agree on every case and assertion count)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
