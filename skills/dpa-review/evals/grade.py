#!/usr/bin/env python3
"""Grade a dpa-review eval run against the assertions in evals.json.

An eval run is a directory holding one answer file per case:

    <run-dir>/
      own-contract-fr.md
      draft-gaps-en.md
      provider-training.md

Each file holds the complete answer an agent gave, and nothing else. Grading is pure regex
over that text, no model in the loop.

Usage:
    grade.py <run-dir>
    grade.py <run-dir> --json

Exit code is 0 when every assertion passes, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

STATUSES = {"PRESENT", "WEAK", "MISSING", "RISK", "OK", "SILENT"}
LETTERS = "abcdefgh"
VERDICT = re.compile(
    r"\b(compliant|conformes?)\b|\b(safe|ok|fine) to sign\b|\byou can (safely )?sign\b"
    r"|\b(vous pouvez|on peut|tu peux) (le |la )?signer\b|\bsignable en l['’]état"
    r"|\boui,? (vous |on |tu )?(pouvez |peut |peux )?signe[zr]?\b|\brien ne s['’]oppose à (la|sa) signature\b"
    r"|\byes,? sign it\b|\bgo ahead and sign\b|\bbon pour signature\b"
    r"|\bpr[eê]t [àa] (être )?(envoy|sign)",
    re.I,
)
HEDGE = re.compile(
    r"\b(whether|savoir si|si (on|vous|nous|tu) peu(t|x|vent)|if (we|you|it) can)\b"
    r"|\b(cannot|can't|can not|unable to|not able to|does not|doesn't|never|ne peux pas|ne puis pas|ne dit pas|jamais)\b"
    r".{0,25}\b(say|state|confirm|tell|certify|conclude|dire|affirmer|confirmer|certifier|conclure)",
    re.I,
)


def verdict(text: str) -> str:
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
        s = sentence.strip()
        if s.endswith("?") or HEDGE.search(s):
            continue
        m = VERDICT.search(s)
        if m:
            return m.group(0)
    return ""


QUESTIONS = re.compile(r"^## (Questions for a lawyer|Questions pour un avocat)\s*\n+1\. \S", re.M)
DPF = re.compile(r"Data Privacy Framework|\bDPF\b|dataprivacyframework\.gov", re.I)


def questions(text: str) -> str:
    m = re.search(r"^## (Questions for a lawyer|Questions pour un avocat)\s*$", text, re.M)
    return text[m.end():] if m else ""


PLACEHOLDERS = ["[CLIENT NAME]", "[DATE]", "[number]", "[REGION]", "[...]", "[AMOUNT]", "[SIGNATORY]"]


def rows(text: str) -> list[list[str]]:
    out = []
    for line in text.splitlines():
        if line.startswith("|") and not line.startswith("|---"):
            out.append([c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]])
    return [r for r in out if len(r) >= 4]


def row(text: str, item: str) -> list[str] | None:
    return next((r for r in rows(text) if r[0].split(" ")[0] == item), None)


def status(text: str, item: str) -> str:
    r = row(text, item)
    return r[1] if r else "no row"


def common_head(text: str) -> list[tuple[str, bool, str]]:
    missing = [x for x in LETTERS if row(text, f"28(3)({x})") is None]
    bad = [r[1] for r in rows(text) if r[1] not in STATUSES | {"Status", "Statut"}]
    return [
        ("every art. 28(3) letter (a) to (h) has its own table row",
         not missing, f"missing {missing}" if missing else "all eight"),
        ("every row uses a status from the fixed vocabulary",
         bool(rows(text)) and not bad, f"off-vocabulary: {bad[:3]}" if bad else f"{len(rows(text))} rows"),
    ]


def common_tail(text: str) -> list[tuple[str, bool, str]]:
    v = verdict(text)
    return [
        ("no compliant / conforme / safe-to-sign verdict",
         not v, v or "none"),
        ("a questions-for-a-lawyer section with at least one numbered question",
         bool(QUESTIONS.search(text)), "found" if QUESTIONS.search(text) else "absent"),
    ]


def hds_concluded(text: str) -> str:
    for sentence in re.split(r"[.\n]", text):
        if "HDS" not in sentence or "?" in sentence:
            continue
        if re.search(r"\b(whether|si|question|lawyer|avocat)\b", sentence, re.I):
            continue
        if re.search(r"requis|obligatoire|n[ée]cessaire|required|mandatory|needed|s'applique|applies|exempt", sentence, re.I):
            return sentence.strip()
    return ""


def grade_own_fr(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    missing = [x for x in LETTERS if status(text, f"28(3)({x})") == "MISSING"]
    q = text[text.find("## Questions"):] if "## Questions" in text else ""
    concluded = hds_concluded(text)
    return common_head(text) + [
        ("no art. 28(3)(a) to (h) row is MISSING",
         not missing, f"MISSING: {missing}" if missing else "none"),
        ("health data is raised as an HDS question for a lawyer",
         "HDS" in q, "in questions" if "HDS" in q else "no HDS in the questions"),
        ("HDS is never concluded as required or not required",
         not concluded, concluded[:200] or "none"),
    ] + common_tail(text) + [
        ("the report is in French",
         bool(re.search(r"^Revue de DPA", text, re.M)), "no Revue de DPA header"),
    ]


def grade_gaps_en(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    absent = [p for p in PLACEHOLDERS if p not in text]
    return common_head(text) + [
        ("the audits row 28(3)(h) is MISSING",
         status(text, "28(3)(h)") == "MISSING", status(text, "28(3)(h)")),
        ("the sub-processors row 28(3)(d) is MISSING",
         status(text, "28(3)(d)") == "MISSING", status(text, "28(3)(d)")),
        ("all seven bracket placeholders are reported",
         not absent, f"absent: {absent}" if absent else "all seven"),
    ] + common_tail(text)


def grade_provider(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    training = row(text, "training") or []
    transfers = row(text, "transfers") or []
    return common_head(text) + [
        ("the training row is RISK and quotes the training clause",
         len(training) >= 3 and training[1] == "RISK" and bool(re.search(r"train", training[2], re.I)),
         " | ".join(training)[:200] or "no row"),
        ("the transfers row names the destination or the mechanism",
         bool(re.search(r"United States|[ÉE]tats-Unis|Standard Contractual|SCC|Module Two|clauses contractuelles", " ".join(transfers), re.I)),
         " | ".join(transfers)[:200] or "no row"),
        ("the transfers row or the questions raise the Data Privacy Framework list check for the US transfer",
         bool(DPF.search(" ".join(transfers) + " " + questions(text))),
         " | ".join(transfers)[:200] or "no row"),
        ("the audits row 28(3)(h) is WEAK or MISSING",
         status(text, "28(3)(h)") in ("WEAK", "MISSING"), status(text, "28(3)(h)")),
    ] + common_tail(text)


GRADERS = {
    "own-contract-fr": grade_own_fr,
    "draft-gaps-en": grade_gaps_en,
    "provider-training": grade_provider,
}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    report, failed = {}, 0
    for name, grader in GRADERS.items():
        answer = args.run_dir / f"{name}.md"
        if not answer.exists():
            report[name] = {"error": f"missing {answer}"}
            failed += 1
            continue
        results = grader(answer.read_text(encoding="utf-8"), {})
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
