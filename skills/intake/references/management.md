# Management

Covers 1:1 preparation, sprint and roadmap planning, estimation, tech arbitration (build vs buy, library choice), and incident or stakeholder communication.

## Look at (Phase 1)

- The board and the tickets in scope, through the issue-tracker MCP.
- PR and commit activity (`gh`, `git log`) for the repos concerned.
- Prior decisions (ADRs, decision records) on the topic.
- The calendar, if one is connected, for dates and attendees.

## Claims to verify

- "Velocity is X", "we ship N per sprint".
- "Y is blocked", "Y is late".
- "Option A is cheaper", "library B is maintained".

## Checks

- Pull every number from its source (an issue-tracker query, `gh`, `git log`) and cite the query.
- Label each judgement call as a judgement, separate from the data.
- For a library or vendor: release history, open issues and licence, read on the day.
- Estimate bottom-up: grep the places to change, split mechanical from judgement cases, size one typical case, multiply; give a range and the assumption that would move it most.

## Done when

The user approves the artifact: a decision record (context, options, decision, consequences, owner, review date), an agenda, a plan or a draft message. Sending it, posting it or creating calendar events is a separately confirmed action.

## Pitfalls

- Invented metrics, or a number with no query behind it.
- Deciding for the user: lay out the options and a recommendation; the user decides.
- Sending, posting or inviting without approval.
- Collecting personal data about people beyond what the task needs: a 1:1 prep stays on the work and on what the user chooses to bring.
