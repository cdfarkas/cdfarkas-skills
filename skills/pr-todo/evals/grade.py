#!/usr/bin/env python3
"""Grade a pr-todo eval run against the assertions in evals.json.

An eval run is a directory holding one answer file per case:

    <run-dir>/
      own-prs-md.md
      other-dev-slack.md
      unknown-user.md

Each file holds the complete answer an agent gave, and nothing else. Grading is
pure regex over that text — no model in the loop — so the same run grades the
same way every time and a disagreement is a bug in the assertion, not noise.

Usage:
    grade.py <run-dir> --org ORG --user USER --other OTHER_USER --unknown UNKNOWN_USER
    grade.py <run-dir> ... --json     # machine-readable

Exit code is 0 when every assertion passes, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

STATUS = r"(draft|conflict|ci-failing|behind|blocked|ready|unknown)"
BLOCKER = re.compile(
    r"(conflicts|ci: |unresolved thread|awaiting review|needs approval"
    r"|behind base|changes requested|review required)"
)
PR_MD = re.compile(r"\[[A-Za-z0-9._-]+#\d+\]\(https://github\.com/[^/]+/[A-Za-z0-9._-]+/pull/\d+\)")
PR_SLACK = re.compile(r"<https://github\.com/[^/]+/[A-Za-z0-9._-]+/pull/\d+\|[A-Za-z0-9._-]+#\d+>")


def nonempty(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines() if line.strip()]


def grade_own_prs(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    lines = nonempty(text)
    first = lines[0] if lines else ""
    rows = [l for l in lines if l.startswith("| [")]
    extra = [l for l in lines if not l.startswith("|") and l != first]
    return [
        ("header names the user, the org and a count",
         bool(re.fullmatch(rf"PR to-do · @{ctx['user']} · {ctx['org']} · \d{{4}}-\d{{2}}-\d{{2}} · \d+", first)),
         first),
        ("markdown table with the six documented columns",
         "| PR | Role | Status | Blockers | Age | Title |" in text,
         next((l for l in lines if l.startswith("| PR")), "no table header")),
        ("every row carries a clickable pull-request link",
         bool(rows) and all(PR_MD.search(r) for r in rows),
         f"{len(rows)} rows"),
        ("no prose around the table",
         not extra,
         " // ".join(extra[:3]) if extra else "none"),
        ("at least one row names a concrete blocking reason",
         any(BLOCKER.search(r) for r in rows),
         next((r for r in rows if BLOCKER.search(r)), "none")),
        ("the developer's own PRs are reported",
         any(("author" in r.split("|")[2] or "assignee" in r.split("|")[2])
             for r in rows if r.count("|") >= 3),
         "none found"),
        ("every row uses a status from the fixed vocabulary",
         bool(rows) and all(re.search(rf"\| {STATUS} \|", r) for r in rows),
         "ok" if rows else "no rows"),
    ]


def grade_slack(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    lines = nonempty(text)
    first = lines[0] if lines else ""
    rows = [l for l in lines if l.startswith("• ")]
    extra = [l for l in lines if not l.startswith("• ") and l != first]
    clean = "|---" not in text and not PR_MD.search(text)
    return [
        ("bold mrkdwn header names the other developer",
         bool(re.fullmatch(rf"\*PR to-do · @{ctx['other']} · {ctx['org']} · \d{{4}}-\d{{2}}-\d{{2}} · \d+\*", first)),
         first),
        ("every bullet carries a Slack mrkdwn link",
         bool(rows) and all(PR_SLACK.search(r) for r in rows),
         f"{len(rows)} bullets"),
        ("no markdown Slack would not render",
         clean,
         "clean" if clean else "markdown table or link syntax found"),
        ("no prose around the bullets",
         not extra,
         " // ".join(extra[:3]) if extra else "none"),
        ("every bullet uses a status from the fixed vocabulary",
         bool(rows) and all(re.search(rf" · {STATUS} · ", r) for r in rows),
         "ok" if rows else "no bullets"),
        ("blocking reasons appear on at least one bullet",
         any(BLOCKER.search(r) for r in rows),
         next((r for r in rows if BLOCKER.search(r)), "none")),
    ]


def grade_unknown(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    lines = nonempty(text)
    said = f"unknown GitHub user: {ctx['unknown']}" in text
    invented = "nothing to do" in text or "| PR |" in text
    return [
        ("the answer says the login does not exist",
         said,
         lines[0] if lines else "empty"),
        ("no invented table and no empty report for a bogus login",
         not invented,
         "clean" if not invented else "reported an empty list instead"),
        ("raw: one line, no explanation around the error",
         len(lines) == 1,
         f"{len(lines)} non-empty lines"),
    ]


GRADERS = {
    "own-prs-md": grade_own_prs,
    "other-dev-slack": grade_slack,
    "unknown-user": grade_unknown,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--org", required=True)
    ap.add_argument("--user", required=True)
    ap.add_argument("--other", required=True)
    ap.add_argument("--unknown", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ctx = {"org": args.org, "user": args.user, "other": args.other, "unknown": args.unknown}
    report, failed = {}, 0

    for name, grader in GRADERS.items():
        answer = args.run_dir / f"{name}.md"
        if not answer.exists():
            report[name] = {"error": f"missing {answer}"}
            failed += 1
            continue
        results = grader(answer.read_text(), ctx)
        report[name] = {
            "passed": sum(1 for _, ok, _ in results if ok),
            "total": len(results),
            "expectations": [{"text": t, "passed": ok, "evidence": ev[:200]} for t, ok, ev in results],
        }
        failed += sum(1 for _, ok, _ in results if not ok)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for name, res in report.items():
            if "error" in res:
                print(f"{name}: {res['error']}")
                continue
            print(f"{name}: {res['passed']}/{res['total']}")
            for e in res["expectations"]:
                if not e["passed"]:
                    print(f"  FAIL  {e['text']}\n        {e['evidence']}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
