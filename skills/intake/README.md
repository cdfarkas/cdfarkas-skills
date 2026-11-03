# intake

A front door for any new piece of work, before anything is designed: a feature, a bug, a
ticket, a backend change, a management decision. It triages the need, looks at what exists,
interviews you about what the code cannot answer, verifies every load-bearing claim in a
ledger (the ticket, your own words and its own inferences included), reproduces when the
result can change the design, and only then writes a one-screen brief that a devil's-advocate
subagent attacks before you approve it. Nothing is edited, created, posted or sent before your
yes.

It exists for three failures: designing on a premise nobody checked, asking you what the code
could answer, and declaring done without evidence. Content it reads (tickets, docs, code
comments, tool output) is data: an instruction hidden in it is quoted to you and not followed.

## Install

```
/plugin marketplace add cdfarkas/cdfarkas-skills
/plugin install intake@cdfarkas-skills
```

Or copy this folder into `~/.claude/skills/` (or your agent's equivalent). Needs `bash`;
`git` and `node` sharpen the facts (git state, `package.json` scripts). The local agents
`devils-advocate` and `finding-verifier` are used when present, else a `general-purpose`
subagent takes their brief.

## Usage

```
/intake <need | ticket key | link> [--deep]
```

- "/intake fix SHOP-142", "/intake add a clear-cart button to the cart page", "/intake
  prépare l'arbitrage Redux ou Zustand pour le comité de vendredi".
- `--deep`: for architectural, multi-repo or unclear work: a longer interview, an independent
  verifier on the riskiest claims, and options plus Given/When/Then scenarios in the brief.
- A trivial change (a typo, one known line) skips the skill; it says so and acts.

It speaks your language in every turn and writes files in English unless you ask otherwise.
The phases print as they run: the triage line `type · size · mode`, then
`[intake N/5] <phase> — <what and why>`, naming the model of every subagent it dispatches.

## The facts script

Phase 1 opens with `scripts/intake-facts.sh`, printed unchanged: what the agent would
otherwise rediscover by hand, and what decides whether a Done-when command can run at all.
Read-only; `--fetch` refreshes the upstream before counting ahead/behind (network).

On a copy of the `cart-button` fixture, on a machine with no local agents:

```
root: /tmp/tmp.Iu79p1Px8o/cart-button
git: not a git repository
instructions: none
adr: none
package manager: unknown (package.json, no lockfile)
script test: vitest run
script lint: eslint src
script typecheck: none
script build: none
dependencies: not installed (no node_modules)
agent devils-advocate: no (fallback: general-purpose)
agent finding-verifier: no (fallback: general-purpose)
```

`dependencies: not installed` is the line that matters here: a brief that promised "`npm
test` passes" would be promising a run that cannot happen until you install. Every line and
its values: [reference.md](reference.md), "Facts".

## What a first reply looks like

From a development run of the previous version (before the facts script), on the
`refuted-ticket` fixture, abridged. The ticket blames an empty cart; the skill checks it first:

```
| # | Affirmation | Source | Vérification | Verdict | Preuve |
|---|---|---|---|---|---|
| 1 | `computeTotal` plante sur un panier vide | ticket | `node -e` : `computeTotal([])` | **réfutée** | `=> 0` : `reduce` a une valeur initiale `0` (`src/cart.js:2`) |
| 2 | Cliquer « Payer » avec un panier vide lève une `TypeError … 'price'` | ticket | `onPay({items:[]})` | **réfutée** | `=> {"error":"EMPTY_CART"}`. La garde est en `src/checkout.js:4-6` |
| 4 | Ce message d'erreur exact apparaît quand **un élément** du panier vaut `undefined` | inférence | `onPay({items:[undefined]})` | vérifiée (sur le code) | `THROWS TypeError: Cannot read properties of undefined (reading 'price')` |

**Je m'arrête ici : la prémisse de SHOP-142 est réfutée (lignes 1-2).**
…
1. **Quel objectif ?** (je recommande a)
```

The ledger columns, verdicts, brief sections and the devil's advocate's fields:
[reference.md](reference.md). The per-type checks (frontend/UI, backend, ticket, management)
and the devil's-advocate prompt: `references/`.

## Evaluation

Four multi-turn prompts on committed fixtures (`evals/fixtures/`): a ticket with a false
premise, a UI request with a false claim about the code, a tech arbitration on a false "used
everywhere", and a ticket that hides an instruction to AI assistants. `evals/run.sh` runs each
one headless, with and without the skill, and `evals/grade.py` grades the answer by regex,
crediting substance in French or English rather than the skill's vocabulary.

Run on 2026-11-03 on Opus, one run per case and arm: **33/34 with the skill, 19/34 without**
(8/9, 10/10, 9/9, 6/6 against 6/9, 3/10, 7/9, 3/6), at about 149 s and 524k tokens per case
against 94 s and 420k. Every baseline found the technical truth; what they skipped was the
process. They edited code or published a deliverable before asking anything, installed packages
and changed a shared component unasked, and marked the trapped ticket resolved, mentioning its
hidden note only afterwards. The skill's one miss: a Done-when that was a sign-off, not a
check. One run per arm and a grader tuned on these cases (no holdout) make these indicative.
Details, grader fixes included: [`evals/RESULTS.md`](evals/RESULTS.md).
