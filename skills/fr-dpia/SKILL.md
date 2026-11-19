---
name: fr-dpia
description: >
  Decide whether a French AIPD / GDPR data protection impact assessment (DPIA, art. 35) is
  required, then draft it in the CNIL PIA structure: context, fundamental principles, the
  three risks on the CNIL four-level severity and likelihood scales, action plan, residual
  risks and the art. 36 prior-consultation question for the DPO. Checks the nine EDPB WP248
  criteria and the CNIL list (deliberation 2018-327). Unknown facts stay explicit TODO
  questions, and nothing is ever presented as validated or compliant. Use for "do I need an
  AIPD / a DPIA", "analyse d'impact", "draft a DPIA / rédige l'AIPD", a new processing of
  sensitive, health, children's, employee or location data, or a risk assessment on the
  CNIL scales. Not legal advice: every verdict ends with "to confirm with the DPO".
license: Apache-2.0
---

# fr-dpia

One script holds the rules: which criteria count, the verdict, the CNIL scales, the draft's
structure and every TODO. Your job is to put the project's facts into an answers file, run
the script, and relay its output. Never write a verdict, a scale value or a section yourself.

## 1. Collect the facts

Read what the person said, and the project when there is one (README, data model, API, any
privacy notes). Each fact you put in the answers file must come from there. A fact you
cannot point to stays `unknown`: the script turns it into a TODO question. Do not estimate
severity or likelihood unless the person gave you the impacts and the threats to base it on.

## 2. Write the answers file

```bash
mkdir -p docs/dpia
bash <skill-dir>/scripts/fr-dpia.sh init > docs/dpia/<slug>.answers.txt
```

`<skill-dir>` is the directory holding this file; `<slug>` names the processing
(`hr-analytics`). Files live in the project, at `docs/dpia/` unless the person names another
place, never in a temporary directory: the person completes the answers file and re-runs.
If the answers file already exists, edit it instead of running `init` again. Fill it in place:

| Key | Value |
|---|---|
| `c1` to `c9` (criteria), `l1` to `l14` (CNIL list) | `yes \| <the project fact that meets it>`, `no \| <why not>`, or `unknown` |
| text keys (`purposes`, `data`, `retention`, ...) | the fact, or leave empty |
| `<risk>_severity`, `<risk>_likelihood` | `1` to `4` or the CNIL label, or `unknown` |

The file's comments name each criterion, list item and question. Format details:
[reference.md](reference.md).

## 3. Run the command that answers the request

| The person asks | Run |
|---|---|
| "do I need an AIPD / a DPIA?" | `bash <skill-dir>/scripts/fr-dpia.sh check docs/dpia/<slug>.answers.txt` |
| "draft / write the DPIA" | `bash <skill-dir>/scripts/fr-dpia.sh render docs/dpia/<slug>.answers.txt --out docs/dpia/<slug>.md` |
| where one risk sits on the CNIL scales | `bash <skill-dir>/scripts/fr-dpia.sh risk <severity> <likelihood>` |

`check` prints the criteria count (`N/9 met, M unknown`), one line per criterion with its
fact or a TODO, the CNIL list result, a `Reason:` line and a `Verdict:` line. `render --out`
writes the draft (`check` as section 0) to the file and prints a summary: the draft path, the
same check block, the art. 36 question for the DPO, and every TODO question keyed by its
answers-file key. `risk` prints one line: the two CNIL labels, the map position
`G<severity>/V<likelihood>`, and whether the pair has the shape of the WP248 example of a
high residual risk.

Your answer always contains the script's stdout verbatim, in a code block: for `check`, the
whole check block; for `render --out`, the whole summary (draft path, check block with its
`Verdict:` line, art. 36 question, TODO questions). Never paraphrase it ("one of the nine")
or cut it to a selection. Add the answers file path, then offer to re-run once the person
answers the TODO questions.

## 4. What you must not do

- Never write that the processing or the DPIA is validated, compliant, "conforme" or
  "validée". Validation is the controller's decision after the DPO's advice.
- Never conclude on prior consultation (art. 36): it is a question for the DPO.
- Never replace a TODO with a guess, and never drop the `to confirm with the DPO` line.

## Failures

The script exits 2 with one `fr-dpia: ...` line on stderr: a missing answers file, a
criterion that is not `yes`, `no` or `unknown`, a severity or likelihood outside 1-4. Fix the
answers file and re-run; do not hand-write the output instead.
