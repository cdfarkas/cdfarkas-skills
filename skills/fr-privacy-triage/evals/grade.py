#!/usr/bin/env python3
"""Grade a fr-privacy-triage eval run against the assertions in evals.json.

An eval run is a directory holding, per case, the answer and the question list the
project was left with:

    <run-dir>/
      llm-api-child-reports.md              the complete answer, nothing else
      llm-api-child-reports.questions.md    copy of docs/lawyer-questions.md after the run
      ...

A missing .questions.md means the run left no question list. Grading is pure regex,
no model in the loop.

Usage:
    grade.py <run-dir> [--json]

Exit code is 0 when every assertion passes, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CLASSES = ("SETTLED", "OFFICIAL", "OPEN")
VERDICT = re.compile(r"\b(non[- ])?(compliant|conformes?)\b", re.I)
OFFICIAL_URL = re.compile(
    r"https://([a-z0-9-]+\.)*(cnil\.fr|legifrance\.gouv\.fr|esante\.gouv\.fr|edpb\.europa\.eu|eur-lex\.europa\.eu)\b")
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
HEALTH = re.compile(r"donn[ée]es? de sant[ée]|health data|\bHDS\b", re.I)
DPIA = re.compile(r"\b(DPIA|AIPD)\b", re.I)
DPIA_VERDICT = re.compile(
    r"(^\W*(yes|no|oui|non)\W+(very |très |most |fort )?(likely|probably|probablement|certainly|certainement)"
    r"|you (do not|don't|do|will|won't|will not|must|should) (need|carry out|do|run) an? (DPIA|AIPD)"
    r"|(vous )?(n')?(avez|aurez|devez|devrez|faut|faudra) (pas )?(besoin d'|faire |réaliser |mener )?(une )?(DPIA|AIPD)"
    r"|pas besoin d'(une )?(DPIA|AIPD)"
    r"|(a |an |une )?(DPIA|AIPD|analyse d'impact( \((DPIA|AIPD)\))?) (is|est|n'est) "
    r"((very |très )?(likely |probably |probablement |certainly |certainement )?)(not |pas )?"
    r"(required|needed|mandatory|obligatoire|n[ée]cessaire|requise?))",
    re.I | re.M)


def nonempty(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def final_table(text: str) -> tuple[bool, list[list[str]], str]:
    """The last table with a Classification column, trailing prose allowed; returns (ok, rows, evidence)."""
    blocks, cur = [], []
    for line in nonempty(text):
        if line.startswith("|"):
            cur.append(line)
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    head = re.compile(r"\|\s*Point\s*\|\s*Classification\s*\|\s*Reference\s*\|", re.I)
    tables = [b for b in blocks if head.match(b[0])]
    if not tables:
        return False, [], "no table with a Classification column"
    block = tables[-1]
    rows = [[c.strip() for c in re.split(r"(?<!\\)\|", r.strip("|"))] for r in block[2:]]
    bad = [r for r in rows if len(r) < 3 or r[1].strip("*` ") not in CLASSES]
    if not rows or bad:
        return False, rows, f"{len(rows)} rows, {len(bad)} unclassified"
    for r in rows:
        r[1] = r[1].strip("*` ")
    return True, rows, f"{len(rows)} rows"


def of_class(rows: list[list[str]], cls: str) -> list[list[str]]:
    return [r for r in rows if r[1] == cls]


def official_ok(rows: list[list[str]], required: bool) -> tuple[bool, str]:
    off = of_class(rows, "OFFICIAL")
    bad = [r[0] for r in off if not (OFFICIAL_URL.search(r[2]) and DATE.search(r[2]))]
    if required and not off:
        return False, "no OFFICIAL row"
    return not bad, f"{len(off)} OFFICIAL rows" + (f", without official URL or date: {bad[:2]}" if bad else "")


def added_later_items(ctx: dict, case: str) -> list[str] | None:
    path = Path(ctx["run_dir"]) / f"{case}.questions.md"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^## Added later\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return []
    return [i for i in re.split(r"^(?=[-*] |\d+[.)] )", m.group(1), flags=re.M) if re.match(r"[-*] |\d+[.)] ", i)]


def common(text: str) -> tuple[list[tuple[str, bool, str]], list[list[str]]]:
    verdict = VERDICT.search(text)
    ok, rows, ev = final_table(text)
    return [
        ("no compliant / conforme verdict", not verdict, verdict.group(0) if verdict else "none"),
        ("has the classification table, every row SETTLED, OFFICIAL or OPEN", ok, ev),
    ], rows


def items_check(text: str, ctx: dict, case: str, pattern: re.Pattern | None = None) -> tuple[str, bool, str]:
    items = added_later_items(ctx, case)
    if items is None:
        return ("question list has a matching item under ## Added later", False, "no question list")
    hits = [i for i in items if pattern is None or pattern.search(i)]
    return ("question list has a matching item under ## Added later", bool(hits),
            f"{len(items)} items, {len(hits)} matching")


def grade_llm_api(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    out, rows = common(text)
    off, off_ev = official_ok(rows, required=True)
    health = HEALTH.search(text)
    settled = of_class(rows, "SETTLED")
    return out + [
        ("at least one OPEN row", bool(of_class(rows, "OPEN")), f"{len(of_class(rows, 'OPEN'))} OPEN"),
        ("an OFFICIAL row, each with an official URL and a date", off, off_ev),
        items_check(text, ctx, "llm-api-child-reports"),
        ("names health data or HDS", bool(health), health.group(0) if health else "none"),
        ("no SETTLED row without a decision log", not settled, f"{len(settled)} SETTLED"),
    ]


def grade_dpia(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    out, rows = common(text)
    dpia_open = [r for r in of_class(rows, "OPEN") if DPIA.search(r[0] + r[2])]
    verdicts = [m.group(0) for m in DPIA_VERDICT.finditer(text)
                if not re.search(r"(whether|if|si|est-ce qu)\W+(\w+\W+){0,3}$", text[max(0, m.start() - 40):m.start()], re.I)
                and "?" not in re.split(r"[.!\n|]", text[m.end():m.end() + 80])[0]]
    checklist = {
        "retention": re.search(r"retention|conservation", text, re.I),
        "DPA": re.search(r"\bDPA\b|article 28|art\. ?28|sous-trait|processor", text, re.I),
        "transfers": re.search(r"outside the (EU|EEA)|hors (de l.)?(UE|EEE|Union)|third countr|transfer", text, re.I),
    }
    missing = [k for k, v in checklist.items() if not v]
    off, off_ev = official_ok(rows, required=False)
    return out + [
        ("a DPIA / AIPD row is OPEN", bool(dpia_open), dpia_open[0][0] if dpia_open else "none"),
        ("no conclusion that a DPIA is or is not required", not verdicts, " // ".join(verdicts[:2]) or "none"),
        ("checklist covers retention, DPA, transfers", not missing, f"missing: {missing}" if missing else "all three"),
        items_check(text, ctx, "dpia-feature", DPIA),
        ("every OFFICIAL row carries an official URL and a date", off, off_ev),
    ]


def grade_voice_notes(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    out, rows = common(text)
    off, off_ev = official_ok(rows, required=True)
    health = HEALTH.search(text)
    french = len(re.findall(r"\b(les|des|est|pour|une|dans|sont)\b", text, re.I))
    return out + [
        ("at least one OPEN row", bool(of_class(rows, "OPEN")), f"{len(of_class(rows, 'OPEN'))} OPEN"),
        ("an OFFICIAL row, each with an official URL and a date", off, off_ev),
        items_check(text, ctx, "voice-notes-local-pc"),
        ("names health data or HDS", bool(health), health.group(0) if health else "none"),
        ("answers in French", french >= 8, f"{french} French function words"),
    ]


def grade_settled(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    out, rows = common(text)
    settled = [r for r in of_class(rows, "SETTLED") if "2026-03-12" in r[2]]
    items = added_later_items(ctx, "settled-by-log")
    retention = [i for i in items or [] if re.search(r"retention|conserv|keep|garder", i, re.I)]
    return out + [
        ("a SETTLED row cites the entry date 2026-03-12", bool(settled), settled[0][0] if settled else "none"),
        ("gives the entry's answer: 30 days", bool(re.search(r"30\s*(days|jours)", text, re.I)), "checked"),
        ("names the entry it relies on", bool(re.search(r"audio retention after transcription", text, re.I)), "checked"),
        ("no retention question appended", not retention,
         "no question list" if items is None else f"{len(retention)} retention items"),
    ]


def grade_conditions(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    out, rows = common(text)
    differ = re.search(
        r"(conditions?|hypoth[eè]ses?)[^\n]{0,160}(diff|chang|ne s.applique plus|no longer|plus valable|ne (sont|est) plus|ne correspond)"
        r"|(diff|chang|ne s.applique plus|no longer|plus valable|ne correspond)[^\n]{0,160}conditions?",
        text, re.I)
    provider = re.compile(r"cloud|transcri|API|prestataire|fournisseur|sous-trait|provider", re.I)
    return out + [
        ("cites the entry date 2026-03-12", "2026-03-12" in text, "checked"),
        ("says the entry's conditions no longer match", bool(differ), differ.group(0)[:120] if differ else "none"),
        ("no SETTLED row", not of_class(rows, "SETTLED"), f"{len(of_class(rows, 'SETTLED'))} SETTLED"),
        ("at least one OPEN row", bool(of_class(rows, "OPEN")), f"{len(of_class(rows, 'OPEN'))} OPEN"),
        items_check(text, ctx, "conditions-differ", provider),
    ]


GRADERS = {
    "llm-api-child-reports": grade_llm_api,
    "dpia-feature": grade_dpia,
    "voice-notes-local-pc": grade_voice_notes,
    "settled-by-log": grade_settled,
    "conditions-differ": grade_conditions,
}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ctx = {"run_dir": str(args.run_dir)}
    report, failed = {}, 0
    for name, grader in GRADERS.items():
        answer = args.run_dir / f"{name}.md"
        if not answer.exists():
            report[name] = {"error": f"missing {answer}"}
            failed += 1
            continue
        results = grader(answer.read_text(encoding="utf-8"), ctx)
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
