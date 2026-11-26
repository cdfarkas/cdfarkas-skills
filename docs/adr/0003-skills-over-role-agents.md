# ADR 0003 — Knowledge goes in skills, and an agent file exists only for a mechanical reason

## Status

Accepted (2026-11-26).

## Context

ADR 0001 says how an agent enters this repository: from an existing one, after a trial against the
generalist. It does not say when an agent file should exist at all. Its context speaks of agents for
several professions, and the first candidate is a role file made mostly of persona prose.

What the sources listed below say:

- A persona in the system prompt does not improve accuracy: no gain over no persona on 2,410 factual
  questions (arXiv 2311.10054), no consistent benefit of expert personas across six models
  (arXiv 2512.05858), and expert personas can improve alignment while they damage accuracy
  (arXiv 2603.18507).
- Curated skills raised the pass rate from 33.9% to 50.5% across 18 model and harness configurations,
  and focused skills with at most three modules beat large bundles (SkillsBench, arXiv 2602.12670).
  The gain fades toward the no-skill baseline when the skill has to be found in a large pool
  (arXiv 2604.04323): a skill that is not loaded brings nothing.
- A skill can set `model`, `allowed-tools` and `disallowed-tools`, but they hold for one turn only. The
  fields of a subagent file (`tools`, `disallowedTools`, `model`, `permissionMode`, `skills`) apply on
  every call (Claude Code docs).
- Anthropic advises against dividing work by type, one agent for features, one for tests, one for
  review: "an agent handling a feature should also handle its tests". Teams with separate agents for
  planning, execution, review and iteration spent more tokens coordinating than executing, and
  multi-agent systems use 3-10x more tokens (January 2026). Subagents stay effective at verification,
  parallel work and modular permissioning (October 2026).

The data trial (`agents/trials/data/RESULTS.md`) is not evidence for this decision: one run per arm,
and both arms passed all 32 checks.

## Decision

1. Profession and domain knowledge goes in a skill: procedures, checklists, references, scripts.
2. An agent file exists only for a mechanical reason, and states it: a check by an agent that did not
   see the work being done, parallel work in fresh contexts, permissions (tools restricted or
   removed), a fixed model, an output contract read by a script, or a behaviour mode that conflicts
   with the session's. It names the skills it preloads in its `skills:` field, its description says
   when to use it, and it carries no persona prose: no identity, character or invented memory.
3. Work is split by context boundary, not by type of work. There is no planner, implementer, tester
   and reviewer chain by default.
4. A skill is small and focused. Its evaluation also checks that it triggers on its eval prompts and
   not on unrelated ones, runs each arm more than once, and on more than one model when possible. A
   result from a single run is marked as such. A change to a skill or an agent proposed by the
   improvement loop is decided by a person.
5. ADR 0001 still applies to every agent file: it starts from an existing one, it is trialled against
   the generalist, and a trial that both arms pass fully is made harder first.
6. Before anyone changes these rules, in this ADR or in the living docs that carry them, they read the
   latest primary sources on the subject: Anthropic docs and engineering posts, recent studies. The
   superseding ADR lists the sources read with the date read. A rule is not changed on memory or
   reputation.

This ADR refines ADR 0001 and does not supersede it.

## Consequences

- An agent per profession is no longer a goal. The open requests for role agents are closed. The
  generalist, with the right skills, stays the answer until a trial shows a measured gain.
- An agent file that cannot name its mechanical reason becomes a skill, or nothing.
- A skill evaluation costs more: repeated runs, a trigger check, a second model.
- Known disagreement: Anthropic's official plugins still ship named role agents (reviewers,
  architects, test engineers, security auditors), and the January 2026 article keeps specialised
  agents with their own prompts when one agent must switch between conflicting behaviour modes. That
  case is one of the mechanical reasons of rule 2.
- A persona can improve alignment, such as tone and safety, while it damages accuracy
  (arXiv 2603.18507). This ADR trades that for accuracy.
- The sources are vendor advice and preprints, and they change: rule 6 makes the next revision read
  them again.

## Sources

All read on 2026-11-26.

- https://claude.com/resources/articles/building-multi-agent-systems-when-and-how-to-use-them
  (Anthropic, 2026-01-23)
- https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop
  (Anthropic, 2026-10-22)
- https://code.claude.com/docs/en/sub-agents (Claude Code docs, undated)
- https://code.claude.com/docs/en/skills (Claude Code docs, undated)
- https://arxiv.org/abs/2311.10054 (submitted 2023-11, revised 2024-10)
- https://arxiv.org/abs/2512.05858 (2025-12-05)
- https://arxiv.org/abs/2603.18507 (2026-03-19)
- https://arxiv.org/abs/2602.12670 (SkillsBench, v4, 2026-06-14)
- https://arxiv.org/abs/2604.04323 (2026-04-06)
- https://github.com/anthropics/claude-plugins-official at commit 0fbfda5 (2026-11-25)
