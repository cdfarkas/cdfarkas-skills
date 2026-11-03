# Ticket (write, refine, triage)

## Look at (Phase 1)

- The ticket through the issue-tracker MCP: description, comments, links and history.
- The linked PRs and the code they touch.
- A duplicate search: same component, same error message, same symptom.

## Claims to verify

The ticket's statements are hypotheses: the repro steps, the impact ("all users", "blocks X"), the onset ("since release X"), the suspected cause.

## Checks

- Reproduce the issue. Before accepting a bug, look for what would make it not one: a guard or caller that already handles it, a library or framework default, config, a test that covers it, docs saying it is intended. Then reachability: can a real user or caller hit this path? A check you cannot run leaves the claim `unverified`, never `refuted`.
- Confirm the scope in the code: which modules, which consumers.
- Find duplicates and related tickets; link them instead of restating them.

## Done when

The user approves the ticket text. Creating, editing or transitioning the ticket in the tracker is a separate action, confirmed on its own.

The text has this shape:
- **Title**: the outcome, not the solution.
- **Context**: what was observed, with the evidence rows from the ledger.
- **Acceptance criteria**: Given/When/Then, each one testable.
- **Out of scope**.
- **Estimate**: with its uncertainty and what it rests on. Estimate bottom-up: grep the places to change, split mechanical from judgement cases, size one typical case, multiply; give a range and the assumption that would move it most.
- **INVEST check**: independent, negotiable, valuable, estimable, small, testable; name any letter that fails.

## Pitfalls

- A solution in the title ("Add a cache to X") instead of the outcome ("X loads in under a second").
- Untestable criteria ("works well", "is fast").
- An invented estimate, or one with no stated basis.
- Rewriting a duplicate instead of linking it.
