#!/usr/bin/env python3
"""Grade an fr-dpia eval run against the assertions in evals.json.

An eval run is a directory holding one answer file per case, plus the draft the agent
saved when there is one (the harness copies it to <case>.draft.md):

    <run-dir>/
      fr-children-reports.md
      en-hr-analytics.md
      en-hr-analytics.draft.md      # optional
      en-newsletter-no-dpia.md

Each <case>.md holds the complete answer an agent gave, and nothing else. Verdict, DPO and
claim assertions read the answer; draft-content assertions (scale labels, feared events,
TODO count) read the answer plus the draft. Grading is pure regex, no model in the loop,
so a rerun grades identically.

Usage:
    grade.py <run-dir>
    grade.py <run-dir> --json     # machine-readable

Exit code is 0 when every assertion passes, 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

COUNT = re.compile(r"\b\d\s*/\s*9\b")
DPO_LINE = re.compile(r"(?i)^.*\b(DPO|DPD|délégué à la protection des données)\b.*$", re.M)
CONFIRM = re.compile(r"(?i)confirm|valid(er|ate)|à vérifier|check with")
ADV = r"(?:(?:fully|entirely|now|already|officially|bien|pleinement|entièrement|déjà)\s+)?"
CLAIM = re.compile(
    r"(?i)\b(?:(?:is|are|was|has been|remains|it's|that's|est|sont|reste|a été|c'est)\s+" + ADV
    + r"(?:GDPR-|RGPD-)?(?:validated|validée?s?|conformes?|compliant|en conformité)\b"
    r"|(?:DPIA|AIPD|processing|traitement)\s+(?:is\s+|est\s+)?(?:validated|validée?)\b"
    r"|(?:status|statut)\s*:\s*(?:validated|validée?)\b)"
)
NEGATION = re.compile(r"(?i)\b(?:not|non|pas|never|jamais|ni|n'est|nor|no|yet)\b|n't\b")
NEUTRAL = re.compile(
    r"(?i)\b(?:to be|must|should|needs?|doit|doivent|faut|once|until|before|unless|if|when|pending|awaiting"
    r"|une fois|avant|jusqu|si|lorsque|tant que|en attente|à faire|à valider|nécessite)\b"
)
LIST_2018_327 = re.compile(r"2018[-‑]327")
VULNERABLE = re.compile(r"(?i)vuln[ée]rab")
D = r"(?:DPIA|AIPD)"
STATUS = r"(?:required|likely|probable|obligatoire|requise|nécessaire|necessary|mandatory|indicated|indiquée|recommended|recommandée|needed)"
REQUIRED_OR_LIKELY = re.compile(
    rf"(?i)\b{D}\s+(?:(?!not\b|non\b|pas\b|n')[\w']+\s+){{0,3}}{STATUS}\b"
    rf"|\b(?:(?:you|we|vous|on)\s+(?:must|need to|should|have to|devez|doit|faut)|il faut|you need)\b[^.;\n]{{0,45}}\b{D}\b"
    rf"|\b(?:required|obligatoire|likely)\b\W+(?:yes|oui)\b"
)
NEGATIVE_VERDICT = re.compile(
    rf"(?i)\b{D}\b[^.;,\n]{{0,25}}?\b(?:not|isn't|non|n'est pas|ne sont pas|pas)\s+(?:strictly\s+|formally\s+)?{STATUS}\b"
    rf"|\b(?:no\s+|pas d'\s*|pas de\s+|aucune?\s+){D}\b[^.;,\n]{{0,25}}?\b{STATUS}\b"
    rf"|\bverdict\W+(?:\w+\s+){{0,2}}not (?:indicated|required|needed)\b"
    rf"|\b(?:don't|do not|doesn't|does not|won't|will not)\s+(?:really\s+|strictly\s+)?(?:need|require)\s+(?:a\s+|an\s+|the\s+)?(?:full\s+|formal\s+)?{D}\b"
    rf"|\bno need (?:for|to (?:do|run|carry out|conduct|perform))\s+(?:a\s+|an\s+)?{D}\b"
    rf"|\bpas\s+(?:besoin|obligé|tenu)\s+(?:d'|de\s+)(?:une\s+|la\s+)?{D}\b"
    rf"|\b{D}\s+(?:is\s+|est\s+)?(?:unnecessary|inutile|not warranted)\b"
)
LEAD_HEDGE = (r"(?:(?:very|most|almost certainly|probably|likely|quite|très|fort|probablement|vraisemblablement"
              r"|sans doute|en principe|a priori|quasi(?:ment)? certainement)\s+)*")
LEAD_END = r"(?=\s*(?:[.,!:;—–]|\*\*|$)|\s+-)"
LEAD_POS = re.compile(rf"(?i)^(?:{LEAD_HEDGE}(?:yes|oui)|pourquoi oui|why yes|en principe (?:requise|obligatoire)){LEAD_END}")
LEAD_NEG = re.compile(rf"(?i)^{LEAD_HEDGE}(?:no|non|not|pas){LEAD_END}")
PASSING = re.compile(
    r"(?i)\b(?:exempt\w*|exempté\w*|dispensé\w*|newsletter|mailing|for example|e\.g\.|par exemple|such as|comme|if|when|unless|whereas"
    r"|si|lorsque|sauf|alors que|contrairement|only|only if|seulement)\b"
)
SEVERITY_LABELS = ("Négligeable", "Limitée", "Importante", "Maximale")
EVENTS = (
    re.compile(r"(?i)illegitimate access|accès illégitime"),
    re.compile(r"(?i)unwanted modification|modification non désirée"),
    re.compile(r"(?i)disappearance of data|disparition de données"),
)
ART36 = re.compile(r"(?i)^.*\b(art(icle|\.)?\s*36|prior consultation|consultation préalable).*$", re.M)
QUESTION = re.compile(r"(?i)\?|question|DPO|DPD")
ART36_CONCLUDED = re.compile(
    r"(?i)(no|not|pas de|aucune)\s+(prior consultation|consultation préalable)\s+(is\s+)?(required|needed|nécessaire|requise)"
)
DRAFT_SECTION = re.compile(r"(?im)^#+\s.*(risks|risques|action plan|plan d'action)")


def dpo_confirmation(text: str) -> tuple[bool, str]:
    lines = [m.group(0) for m in DPO_LINE.finditer(text) if CONFIRM.search(m.group(0))]
    return bool(lines), lines[0][:200] if lines else "no line sends the verdict to the DPO"


def sentences(text: str) -> list[str]:
    return [x for x in re.split(r"(?<=[.!?;])\s+|\n+", text) if x.strip()]


def no_claim(text: str) -> tuple[bool, str]:
    for sent in sentences(text):
        for m in CLAIM.finditer(sent):
            if not NEGATION.search(sent[max(0, m.start() - 30):m.end()]) and not NEUTRAL.search(sent):
                return False, sent[:200]
    return True, "none"


def lead_verdict(text: str) -> tuple[str | None, str | None]:
    """A verdict word opening the answer or a bolded line ("**Probably not.**") decides alone."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    openers = [re.sub(r"^[#>*\s]+", "", lines[0])] if lines else []
    openers += [m.group(1) for m in re.finditer(r"(?m)^\s*\*\*([^*\n]+)\*\*", text)]
    for o in openers:
        if m := LEAD_POS.match(o.strip()):
            return m.group(0), None
        if m := LEAD_NEG.match(o.strip()):
            return None, m.group(0)
    return None, None


def verdict(text: str) -> tuple[str | None, str | None]:
    lead = lead_verdict(text)
    if any(lead):
        return lead
    pos = neg = None
    for sent in sentences(text):
        n = NEGATIVE_VERDICT.search(sent)
        p = REQUIRED_OR_LIKELY.search(sent)
        if n and not PASSING.search(sent):
            neg = neg or n.group(0)
        if p and not n and not PASSING.search(sent):
            pos = pos or p.group(0)
    return pos, neg


def todos(text: str) -> int:
    return len(re.findall(r"\bTODO\b", text))


def grade_children(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    dpo_ok, dpo_ev = dpo_confirmation(text)
    claim_ok, claim_ev = no_claim(text)
    count = COUNT.search(text)
    pos, neg = verdict(text)
    return [
        ("the criteria count out of nine is given", bool(count), count.group(0) if count else "no N/9"),
        ("the vulnerable data subjects criterion is named", bool(VULNERABLE.search(text)), "found" if VULNERABLE.search(text) else "not named"),
        ("the CNIL list, deliberation 2018-327, is consulted", bool(LIST_2018_327.search(text)), "found" if LIST_2018_327.search(text) else "not cited"),
        ("the verdict is required or likely", bool(pos) and not neg, pos or "no required/likely verdict"),
        ("a line sends the verdict to the DPO for confirmation", dpo_ok, dpo_ev),
        ("nothing is claimed validated or compliant", claim_ok, claim_ev),
        ("unknown facts are left as TODO questions", todos(text) >= 1, f"{todos(text)} TODO"),
    ]


def grade_hr(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    dpo_ok, dpo_ev = dpo_confirmation(text)
    claim_ok, claim_ev = no_claim(text)
    count = COUNT.search(text)
    full = text + "\n" + ctx.get("draft", "")
    missing_labels = [l for l in SEVERITY_LABELS if l not in full]
    missing_events = [p.pattern for p in EVENTS if not p.search(full)]
    art36_lines = [m.group(0) for m in ART36.finditer(text)]
    art36_ok = any(QUESTION.search(l) for l in art36_lines) and not ART36_CONCLUDED.search(text)
    return [
        ("the criteria count out of nine is given", bool(count), count.group(0) if count else "no N/9"),
        ("the CNIL list, deliberation 2018-327, is consulted", bool(LIST_2018_327.search(text)), "found" if LIST_2018_327.search(text) else "not cited"),
        ("the CNIL severity scale labels are used", not missing_labels, f"missing {missing_labels}" if missing_labels else "all four"),
        ("the three feared events are each assessed", not missing_events, f"missing {missing_events}" if missing_events else "all three"),
        ("at least five unsupplied facts are TODO markers", todos(full) >= 5, f"{todos(full)} TODO"),
        ("prior consultation (art. 36) is put to the DPO as a question", art36_ok, art36_lines[0][:200] if art36_lines else "art. 36 not raised"),
        ("a line sends the verdict to the DPO for confirmation", dpo_ok, dpo_ev),
        ("nothing is claimed validated or compliant", claim_ok, claim_ev),
    ]


def grade_newsletter(text: str, ctx: dict) -> list[tuple[str, bool, str]]:
    dpo_ok, dpo_ev = dpo_confirmation(text)
    claim_ok, claim_ev = no_claim(text)
    count = COUNT.search(text)
    pos, neg = verdict(text)
    negative = neg or next((m.group(0) for m in map(NEGATIVE_VERDICT.search, sentences(text)) if m), None)
    draft = DRAFT_SECTION.search(text) or DRAFT_SECTION.search(ctx.get("draft", ""))
    return [
        ("the criteria count out of nine is given", bool(count), count.group(0) if count else "no N/9"),
        ("the verdict is that a DPIA is not indicated or not required", bool(negative) and not pos, negative or "no negative verdict"),
        ("a line sends the verdict to the DPO for confirmation", dpo_ok, dpo_ev),
        ("no DPIA draft is produced for a case that does not need one", not draft, draft.group(0) if draft else "none"),
        ("nothing is claimed validated or compliant", claim_ok, claim_ev),
    ]


GRADERS = {
    "fr-children-reports": grade_children,
    "en-hr-analytics": grade_hr,
    "en-newsletter-no-dpia": grade_newsletter,
}


def main() -> int:
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
        draft = args.run_dir / f"{name}.draft.md"
        ctx = {"draft": draft.read_text(encoding="utf-8")} if draft.exists() else {}
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
