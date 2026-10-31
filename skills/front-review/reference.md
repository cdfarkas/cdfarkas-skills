# front-review — reference

What the script prints, the overlay format, the rules with their stable ids, the noise to
avoid, the default floor, and the report contract. `SKILL.md` says when to read each part.

## Script output

`scripts/front-review.sh [<target>] [--lang en|fr]` prints these sections, always in this
order. An empty list prints `- (none)`.

| Section | Content |
|---|---|
| header | `Front review context · <repo or folder> · <kind>` |
| `## Target` | kind, target as given, base ref (where the overlay and contract are read), head ref (where code and gates are read), merge base for diff kinds |
| `## Files (n)` | front files under five groups, each with its axes: `CSS -> A, U`, `TSX/JSX -> R, A, T`, `Stories/tests -> T, U`, `TS/JS -> R`, `Package/build -> P when publishable` |
| `## Overlay (n)` | each `REVIEW.md` covering a changed file, its ref, its scope and the rule ids its `## Do not report` switches off; then the report language and where it came from |
| `## Contract files` | `CLAUDE.md` files in every directory covering a changed file, `.claude/rules/*.md`, ADR folders (`docs/adr`, `docs/adrs`, `docs/decisions`, `doc/adr`, `adr`, `adrs`, `decisions`, `docs/architecture/decisions`) |
| `## Gates` | eslint (with `react-hooks` and `jsx-a11y` yes/no), stylelint, tsc, axe, visual regression, size-limit, each CI workflow with its step names |
| `## Rule switches` | P axis on/off per package, `R11` on/off, the ids each overlay switches off |
| `## Floor in effect` | each overlay's `## Floor` text with its scope, else the default floor below |
| `## Candidates (n)` | `- <id> <file>:<line> <mechanism>`, then `Suppressed by the overlay (n)` with the overlay that switched each one off (hints included) |
| `## Hints (n)` | `- <id> <file>:<line> <mechanism>`: leads the review reports or names on the Not checked line with a reason |
| `## Vocabulary (en|fr)` | the report's section names, closing lines and verdict line |
| `## Overlay text` | the full text of each overlay, between `--- <path> ---` and `--- end <path> ---` |

Paths are relative to the git root for diff kinds and to the target folder for a path target.
A path target also walks the directories above it up to the git root, shown as `../`, for
`REVIEW.md`, `CLAUDE.md`, configs and workflows.

### Target resolution

| Target | Kind | Files | Base (overlay, contract) | Head (code, gates) |
|---|---|---|---|---|
| none | working diff | `git diff <merge-base>` plus untracked files | default branch | working tree |
| digits or a `/pull/<n>` URL | pull request | diff from the merge base to the PR head | `origin/<base branch>` | `pull/<n>/head`, fetched, never checked out |
| an existing path | path | every file under it (git-tracked and untracked, ignored ones skipped) | working tree | working tree |
| contains `..` | revision range | `git diff <range>` | the range start | the range end (`HEAD` when empty) |
| anything else | branch | diff from the merge base to the branch | default branch | the branch |

Default branch: `origin/HEAD`, else the first of `origin/main`, `origin/master`, `main`,
`master` that exists. Deleted files are skipped. A file under `node_modules/`, a `.d.ts`, and
tool configs other than bundler configs are not front files.

### Candidates

Mechanical checks, suppressed only by an overlay that switches the id off for that file. A
**candidate** must appear in the review, as a finding or on the Not checked line. A **hint**
(P1) names a mechanism whose cost depends on judgement: report it as a finding, or name it on
the Not checked line with the reason it was not.

| Id | Fires on | Scope |
|---|---|---|
| A1 | a CSS/SCSS/Sass/Less file with `appearance: none` and no `forced-colors` anywhere in the file; cites the first `appearance: none` line | CSS group |
| R1 | a JSX opening tag where a `{...spread}` follows an `aria-*` attribute; cites the spread line and names the attribute and its line | TSX/JSX group |
| P1 (hint) | a module-level, non-exported object literal whose values read an imported CSS module (`styles.x`) and whose every other use is an index read (`map[key]`; `typeof map` ignored) | TSX/JSX and TS/JS groups, publishable package only |

Publishable: the nearest `package.json` has `exports` or `main` and no `"private": true`.

### Exit codes

| Code | Last stderr line | Cause |
|---|---|---|
| 0 | — | context printed (possibly `Files (0)`) |
| 1 | `not a git repository: <dir>` | a diff or PR target outside a git repo |
| 1 | `unknown revision: <rev>` | the branch or a range end does not resolve |
| 1 | `unknown target: <t> (a range needs a start revision)` | a range like `..main` |
| 1 | `no default branch found (tried origin/HEAD, origin/main, origin/master, main, master)` | working diff or branch target with no default branch |
| 1 | `no merge base between <a> and <b>` | unrelated histories |
| 1 | `gh is required for a pull request target but not found` | install `gh` |
| 1 | `gh pr view <n> failed` | the line above it is `gh`'s own error (no such PR, not authenticated) |
| 1 | `cannot fetch pull request <n> from origin` | network or permissions |
| 1 | `head <sha> of pull request <n> is missing after the fetch` | the PR head moved during the fetch; rerun |
| 2 | `unknown flag: <f>`, `unknown language: <l> (en|fr)`, `--lang needs a value (en|fr)`, `one target only, got: …` | usage error, printed after the usage text |

## Overlay: REVIEW.md

A repo layers its own requirements on the base rules in a `REVIEW.md` at its root, and
optionally another in a subdirectory for the files under it. It is the file name and section
convention of Claude Code's managed Code Review. It holds only what changes the review; general
project context stays in `CLAUDE.md`. Every section is optional freeform Markdown.

| Section | Effect |
|---|---|
| `## Floor` | WCAG level, target size and browser targets the A rules measure against |
| `## Always check` | repo rules, each with an id (`UI-1`…) and the source backing it; applied with the same finding shape and evidence bar |
| `## What Blocking means here` (or `What Bloquant means here`) | recalibrates severity |
| `## Do not report` | gates and paths to skip, and base rule ids switched off |
| `## Gates` | commands the reviewer may run as evidence |
| `## Decisions` | where the decisions that settle disputes live |
| `## Language` | `en` or `fr`: the report language, over the request's |

```markdown
# Review rules for @acme/ui

## Floor
- WCAG 2.1 AA: a failure is Blocking. WCAG 2.2 additions are at most Should fix.
- Target size: 24x24 CSS px (SC 2.5.8), or its spacing exception.

## Always check
- UI-1: every component is exported from `src/index.ts` (source: docs/adr/0003).

## What Blocking means here
- An axe "incomplete" result counts as a violation.

## Do not report
- Contrast pairs: `tokens.test.ts` asserts them. P*: the package is not published yet.

## Gates
- `pnpm test`, `pnpm visual-check <story>`

## Language
fr
```

Rules:

- Precedence: `REVIEW.md` > the repo's `CLAUDE.md`, rules and ADRs > this file.
- Read from the base ref: a pull request cannot relax its own review. A path target reads the
  working tree.
- Ids in `## Do not report` are the tokens matching `[ARUPT]<number>` or `<letter>*` (`P*`
  switches off the whole axis). An id is off for a file when any overlay covering that file
  switches it off. Other lines are instructions for the reviewer, applied as written.
- `## Floor` and `## Language` come from the overlay nearest the root that sets them; a
  subdirectory floor is printed with its scope and applies to the files under it.
- No overlay: the base rules run on the default floor, and the Not checked line says that no
  overlay was found.

## Default floor

- WCAG 2.1 AA (EN 301 549, the European Accessibility Act baseline): a failure is Blocking.
- WCAG 2.2 additions (target size, focus not obscured, dragging): at most Should fix.
- Target size: 24×24 CSS px or the spacing exception (SC 2.5.8). Never 44 px: that is AAA
  (SC 2.5.5) or a platform guideline, not the floor.
- Browsers: as the repo states; unstated means none is assumed.

## Rules

Applies to: **control** (one component), **compound** (parts sharing state), **page** (routes,
data), **tests**, **package** (a publishable package). Control rules apply upward. "Gate"
names the tool that covers the rule when the repo has it configured; a covered rule is
checked only for what the gate cannot see.

### A: accessibility beyond axe (CSS, TSX/JSX)

| Id | Rule | How to verify | Applies to | Gate |
|---|---|---|---|---|
| A1 | Every state drawn with `background-color`, `box-shadow` or `background-image` (typical of `appearance: none` controls) survives forced colors through an `@media (forced-colors: active)` path using system colours, borders or outlines | Render the state matrix with forced colors; grep `forced-colors` | control | visual regression with a forced-colors capture |
| A2 | Every state cue carried by motion keeps a non-motion equivalent under `prefers-reduced-motion`; no global near-zero duration that hides a cue | Compare computed style on hover and active with `reducedMotion: 'reduce'` and without | control | a reduced-motion computed-style test |
| A3 | Targets are at least 24×24 CSS px or the spacing exception holds, at the worst case: no visible label, smallest size, densest documented layout | Measure the box; reason about the densest layout the docs allow, not only the stories | control | axe `target-size` (a WCAG 2.2 rule) on a worst-case story |
| A4 | Visual state, assistive-tech state and form value agree (an invalid border and `aria-invalid`; the displayed state and `checked` under `indeterminate`) | Follow the prop flow; test the override path (`aria-invalid={false}` with `invalid`) | control | none |
| A5 | A control without a visible label has an enforced (required prop type) or documented accessible-name path | Read the prop types and docs; a story with `aria-label` passes axe | control | axe sees a rendered story, not the missing contract |
| A6 | No focus loss on a runtime state change (no remount); the focus ring is visible in every theme | Focus screenshot per theme; check that no component type swaps on state | control | visual regression with a focus capture |
| A7 | No overflow or clipping at 320 CSS px wide and at 200 % text | Render at 320 px with the root font at 200 % | control, page | none |

### R: React and TypeScript (TSX/JSX, TS/JS)

| Id | Rule | How to verify | Applies to | Gate |
|---|---|---|---|---|
| R1 | The spread order of `{...rest}` against contract props (`aria-*`, `data-*` the component sets) is deliberate, consistent across sibling components and tested: a caller prop must not silently override a contract attribute | Read the JSX order; grep the siblings; test the override | control | none |
| R2 | `ref` reaches the native element; a merged ref handles callback refs (with React 19's cleanup return) and object refs | Read the ref merge; test with a callback ref | control | none |
| R3 | DOM-only (IDL) properties such as `indeterminate` are synced after render and re-applied when a native interaction resets them | Read the effect and the handler; a test toggling the prop | control | none |
| R4 | No component-type swap on runtime state: `cond ? <A/> : <B/>` on a stateful part remounts it, losing focus and uncontrolled value | Look for type swaps on stateful parts | control, compound | none |
| R5 | Booleans that mirror one DOM or ARIA state are fine; mode booleans that switch whole subtrees are a finding | Does the boolean select a different subtree? | control, compound | none |
| R6 | A compound component exists only when its parts share state; a context with nothing to share is ceremony | Read what the context carries | compound | none |
| R7 | Effects only synchronise with the DOM or an external system; no derived state computed in an effect | Read every effect | control, compound, page | none |
| R8 | A conditional render cannot print `0` or `NaN` (`count > 0 &&`, not `count &&`) | Read the conditionals | all | none |
| R9 | Labels as `children`, not render props for plain content; no `forwardRef` on React 19 | grep | control | none |
| R10 | A new public component follows the creation process the repo contract documents (naming study, docs page, export), when one is documented | Read the contract files the script lists | control | none |
| R11 | No hook called conditionally or after an early return | Read the hook calls in order | all | eslint `react-hooks/rules-of-hooks`; applied only when the script prints `R11: on` |

### U: UX and UI (CSS, stories)

| Id | Rule | How to verify | Applies to | Gate |
|---|---|---|---|---|
| U1 | Each state (rest, hover, focus, active, disabled, invalid, checked, mixed) is distinguishable in every theme, and not by colour alone | Render the state matrix, plus a hover probe (stories rarely capture hover) | control | visual regression (no hover) |
| U2 | A documented override example does not teach a broken affordance (a round checkbox reads as a radio button) | Render the override story | control | none |
| U3 | Stories or examples cover what the repo's docs or decisions require | Compare the stories with the requirements in the contract files | control | none |
| U4 | Semantic tokens keep their meaning in every theme (muted stays muted) | Compare themes on the same story | control | contrast tests, when the repo has them |
| U5 | Consistent with sibling components: data attributes, motion tokens, size scale, prop names | Read the siblings | control | none |

### P: library performance (publishable package only)

| Id | Rule | How to verify | Applies to | Gate |
|---|---|---|---|---|
| P1 | A consumer importing one export does not carry the others; module-level objects and property reads defeat tree-shaking | Build to a scratch dir, bundle a one-import consumer, compare bytes; name the bundler and the ones not tested | package | `size-limit` with a one-import entry |
| P2 | `sideEffects` and CSS delivery are right, and the cost of a single stylesheet is known | Inspect the build output (does the JS import CSS?); size each component's CSS | package | none |
| P3 | Peer dependencies are externalised (React not bundled) | Inspect the build output | package | none |
| P4 | Transitions avoid layout properties; paint stays small-surface; no `will-change` at rest | Read the CSS | package | none |
| P5 | Per-instance cost when rendered by the hundreds (work per commit) | Measure, only when suspected | package | none |
| P6 | Size and tree-shaking claims in docs or decisions match a fresh measurement | Rebuild and compare | package | `size-limit` |

Measure, never assert: a P finding without a build artefact is PLAUSIBLE at best.

### T: tests (stories, tests, TSX/JSX)

| Id | Rule | How to verify | Applies to | Gate |
|---|---|---|---|---|
| T1 | Tests query by role and accessible name (`getByRole('switch', { name })`), not by test id or class | Read the queries | tests | `eslint-plugin-testing-library`, when configured |
| T2 | Interactions go through `userEvent`, not `fireEvent`, unless one synthetic event is the point of the test | Read the interaction calls | tests | `eslint-plugin-testing-library`, when configured |
| T3 | Tests assert what the user observes (roles, states, text), not implementation (internal state, class names, calls to internals) | Read the assertions | tests | none |
| T4 | No vacuous assertion on a zero-size jsdom render: layout is all zeros in jsdom, so geometry or visibility-by-size asserts pass on anything | Check the environment (jsdom or a real browser) of every layout assertion | tests | none |
| T5 | New logic is guarded: mutate one condition at a time, a named test must fail, restore byte for byte. Sparingly, for logic-bearing changes only | Mutate in a scratch worktree and run that one test | tests | mutation testing, when configured |
| T6 | The public prop contract has type tests (`expectTypeOf`, `@ts-expect-error`), so a contract change that still compiles internally is caught | Look for type tests on the exported prop types | package | `tsc` over the type tests |

## AVOID: noise that is never a finding

| Id | Pattern | Example |
|---|---|---|
| X1 | Keyword matching instead of mechanism | "every boolean prop is a smell" on an `invalid` prop that mirrors `aria-invalid` |
| X2 | Page-level rules on a component: state lifting, route code splitting, font preload, Core Web Vitals | asking an input to lazy-load |
| X3 | Consumer-side bundle rules applied to the library author | barrel imports rated critical on a small single-file package |
| X4 | Generic thresholds over the floor | a 44 px target rule on a 24 px control that meets SC 2.5.8 |
| X5 | Taste rules against a chosen aesthetic | "no custom form controls" in a design system that draws its own |
| X6 | Asking a component to do what the architecture puts elsewhere | error text inside an input when a field wrapper owns it |
| X7 | Memo, `useCallback` or dependency-array reflexes without a measured cost | adding deps to a dependency-less layout effect that re-applies a DOM property a native click resets: the deps would break it |
| X8 | Re-reporting what a gate enforces | a contrast pair a contrast test already asserts |
| X9 | Page heuristics and personas scored on one control | a cognitive-load checklist on a checkbox |
| X10 | A fix that causes harm | splitting a stateful component into variant components that remount on state change |
| X11 | Token pedantry against a repo-wide pattern | flagging a primitive spacing token where no semantic spacing tier exists |
| X12 | Process baggage that fights the repo's governance | mandatory design documents, persisted snapshots, closing question rounds |

## Finding and report

### Finding shape

```
`path:line` — CONFIRMED | PLAUSIBLE — <rule id>
What the code does.
Failure scenario: a concrete input or state → the wrong behaviour.
Evidence: the file:line read, plus the render, computed style, test or measurement it rests on.
Fix: the concrete change.
```

- **E1** Every finding carries `file:line`, a concrete failure scenario, a severity and its
  evidence. CONFIRMED: you read the source that settles it. PLAUSIBLE: one step is unverified,
  and the finding names it. No evidence line, no finding.
- **E2** Contract first: a check that contradicts a locked decision goes on the Conflict line.
- **E3** A visual claim rests on a render; with no render, it is PLAUSIBLE and the probe goes on
  the Not checked line.
- **E4** A performance claim rests on a build artefact and a one-import consumer bundle, naming
  the bundler and the ones not tested.
- **E5** Severity. **Blocking**: a failure at the floor, a state the user cannot perceive,
  broken behaviour or a broken public contract. **Should fix**: real but contained; WCAG 2.2
  rules under the default floor stop here. **Minor**: worth fixing, 5 at most. The overlay's
  `## What Blocking means here` overrides. **Pre-existing**: not introduced by this change.
  **Outside diff**: introduced by it, but the code to fix sits outside every hunk; give its real
  line at the head. A path target has neither: every file is new.
- **E6** Read-only: no fix applied, nothing posted, no binary or rules fetched at review time.
- **E7** The Not checked line names every axis, probe or candidate not verified, and why.
  Rejected candidates are not shown.

### Report

English, with the script's `en` vocabulary:

```
# Review: <target>
<base> ← <head> · overlay: <paths> | none · floor: <source>

## Blocking
## Should fix
## Minor
## Pre-existing
## Outside diff

Not checked: <axes, probes and candidates not verified, and why>
Conflict: <check against a locked decision, only when one exists>
VERDICT: PASS | CHANGES
```

French, with the `fr` vocabulary:

```
# Revue : <cible>
<base> ← <head> · overlay : <chemins> | aucun · plancher : <source>

## Bloquant
## Point d'attention
## Mineur
## Préexistant
## Hors diff

Non vérifié : <axes, sondes et candidats non vérifiés, et pourquoi>
Conflit : <contrôle contre une décision verrouillée, seulement s'il y en a un>
VERDICT: PASS | CHANGES
```

Findings go under their section in the finding shape; empty sections are left out.
`VERDICT: CHANGES` with at least one Blocking finding, else `VERDICT: PASS`, alone on the last
line.
