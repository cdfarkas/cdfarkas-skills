#!/usr/bin/env python3
"""Grade a sentry-triage eval run against the assertions in evals.json.

An eval run is a directory holding one answer file per case:

    <run-dir>/
      url-triage.md
      slack-format.md
      unknown-project.md

Each file holds the complete answer an agent gave, and nothing else. Grading is
pure regex over that text — no model in the loop — so the same run grades the
same way every time and a disagreement is a bug in the assertion, not noise.

Usage:
    grade.py <run-dir> --org ORG --project PROJECT --env ENV --unknown UNKNOWN_PROJECT
    grade.py <run-dir> ... --json     # machine-readable

Exit code is 0 when every assertion passes, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SEV = r"(critical|high|medium|low)"
ORIGIN = r"(app|vendor|network|browser)"
COMPLEXITY = r"\b(S|M|L|M[–-]L|noise)\b"
TABLE_HEADER = "| Issue | Sev | Score | Users | Events | Trend | Status | Origin | Where | Title |"
LINK_MD = re.compile(r"\[[A-Z0-9-]+\]\(https://[^)]+/issues/\d+/?\)")
LINK_SLACK = re.compile(r"<https://[^|>]+/issues/\d+/?\|[A-Z0-9-]+>")
RANKED = re.compile(r"^\s*\d+[.)]\s")


def nonempty(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines() if line.strip()]


def grade_url_triage(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    lines = nonempty(text)
    first = lines[0] if lines else ""
    rows = [l for l in lines if l.startswith("| [")]
    ranked = [l for l in lines if RANKED.match(l)]
    first_ranked = ranked[0] if ranked else ""
    browser_first = bool(re.search(r"\bbrowser\b", first_ranked)) and not re.search(r"\bnoise\b", first_ranked)
    return [
        ("header names org, project, env, period, query and a count",
         bool(re.fullmatch(rf"Sentry triage · {ctx['org']}/{ctx['project']} · {ctx['env']} · 14d · is:unresolved · \d+ issues", first)),
         first),
        ("markdown table with the ten documented columns",
         TABLE_HEADER in text,
         next((l for l in lines if l.startswith("| Issue")), "no table header")),
        ("every row carries a clickable issue link",
         bool(rows) and all(LINK_MD.search(r) for r in rows),
         f"{len(rows)} rows"),
        ("every row has a severity and an origin from the fixed vocabularies",
         bool(rows) and all(re.search(rf"\| {SEV} \|", r) and re.search(rf"\| {ORIGIN} \|", r) for r in rows),
         "ok" if rows else "no rows"),
        ("a Clusters block follows the table",
         "Clusters (one root cause, fix once):" in text,
         "present" if "Clusters" in text else "absent"),
        ("a numbered ranked list follows, at most 10 entries",
         0 < len(ranked) <= 10,
         f"{len(ranked)} entries"),
        ("every ranked entry names a severity and a complexity",
         bool(ranked) and all(re.search(rf"\b{SEV}\b", r) and re.search(COMPLEXITY, r) for r in ranked),
         next((r for r in ranked if not (re.search(rf"\b{SEV}\b", r) and re.search(COMPLEXITY, r))), "ok")),
        ("a browser-origin issue is not ranked first unless marked noise",
         not browser_first,
         first_ranked or "no ranked list"),
    ]


def grade_slack(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    lines = nonempty(text)
    first = lines[0] if lines else ""
    rows = [l for l in lines if l.startswith("• <")]
    clean = "|---" not in text and not LINK_MD.search(text)
    return [
        ("bold mrkdwn header names org, project and env",
         bool(re.fullmatch(rf"\*Sentry triage · {ctx['org']}/{ctx['project']} · {ctx['env']} · 14d · is:unresolved · \d+ issues\*", first)),
         first),
        ("every issue bullet carries a Slack mrkdwn link",
         bool(rows) and all(LINK_SLACK.search(r) for r in rows),
         f"{len(rows)} bullets"),
        ("no markdown Slack would not render",
         clean,
         "clean" if clean else "markdown table or link syntax found"),
        ("every issue bullet has a severity from the fixed vocabulary",
         bool(rows) and all(re.search(rf" · {SEV} \d+ · ", r) for r in rows),
         "ok" if rows else "no bullets"),
    ]


def grade_unknown(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    lines = nonempty(text)
    said = f"unknown project '{ctx['unknown']}' in organization {ctx['org']}" in text
    invented = "no issues" in text or "| Issue |" in text or any(RANKED.match(l) for l in lines)
    return [
        ("the answer says the project is unknown",
         said,
         lines[0] if lines else "empty"),
        ("no invented table, empty report or ranking for a bogus project",
         not invented,
         "clean" if not invented else "reported a result instead"),
        ("raw: one line, no explanation around the error",
         len(lines) == 1,
         f"{len(lines)} non-empty lines"),
    ]


GRADERS = {
    "url-triage": grade_url_triage,
    "slack-format": grade_slack,
    "unknown-project": grade_unknown,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--org", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--env", required=True)
    ap.add_argument("--unknown", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ctx = {"org": args.org, "project": args.project, "env": args.env, "unknown": args.unknown}
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
