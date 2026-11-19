# fr-dpia

Is a French AIPD / GDPR data protection impact assessment (DPIA, art. 35) required, and
what would it say? The script checks the nine EDPB WP248 criteria and the CNIL list
(deliberation 2018-327), then drafts the DPIA in the CNIL PIA structure. Every fact nobody
supplied stays a `TODO` question, and every verdict ends with "to confirm with the DPO".
It drafts, it never validates.

```
fr-dpia check · HR analytics tool · 2026-11-19

Criteria (EDPB WP248 rev.01, CNIL deliberation 2018-326): 2/9 met, 7 unknown
- [yes] 1. evaluation or scoring, including profiling — ranks employees by an attrition-risk score
- [unknown] 2. automated decision-making with legal or similar significant effect — TODO: is this criterion met, and by which fact?
...
- [yes] 7. data concerning vulnerable data subjects — employees of the controller
...
CNIL list (deliberation 2018-327): matched
- item 3: Traitements établissant des profils de personnes physiques à des fins de gestion des ressources humaines — builds per-employee profiles for HR decisions
Reason: the processing is on the CNIL list
Verdict: DPIA required — to confirm with the DPO
```

## Usage

```
bash scripts/fr-dpia.sh init > answers.txt      # blank answers file, every answer "unknown"
bash scripts/fr-dpia.sh check answers.txt       # criteria count, CNIL list, verdict
bash scripts/fr-dpia.sh render answers.txt      # the DPIA draft in markdown, to stdout
bash scripts/fr-dpia.sh render answers.txt --out docs/dpia/hr.md
                                                # the draft to a file; stdout gets the summary
bash scripts/fr-dpia.sh risk 4 2                # one risk on the CNIL scales
```

`render` follows the CNIL method: context, fundamental principles (necessity,
proportionality, rights), the three risks (illegitimate access, unwanted modification,
disappearance) with impacts, sources, threats, measures, severity and likelihood on the CNIL
four-level scales, an action plan, the residual-risk table and the art. 36 question for the
DPO, then validation left open. Without `--out` everything goes to stdout. With `--out` the
draft goes to that file (its directory is created) and stdout gets the summary the agent
relays: the draft path, the check block, the art. 36 question and every TODO question keyed
by its answers-file key. The skill keeps both files in the project, under `docs/dpia/`.
Needs only bash.

Answers file format, verdict rules, scales and the official sources each rule comes from:
[`reference.md`](reference.md). The official pages it relies on, with a verbatim quote each and
whether they were read, are listed in [`sources.json`](sources.json).

## Evaluation

With the skill 7/7, 8/8, 4/5 (19/20); without 5/7, 1/8, 3/5 (9/20), one run per case on
2026-11-19. The one failure is `en-newsletter-no-dpia`: the skill answered "DPIA
undetermined" on a form that stores an email and a date, because three criteria were
unknown, where the case expected "not indicated". The skill is stricter than the case; the
assertion was left as written. Method, caveats and the baseline comparison are in
[`evals/RESULTS.md`](evals/RESULTS.md).
