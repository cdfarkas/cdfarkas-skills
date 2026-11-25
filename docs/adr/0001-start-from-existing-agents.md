# ADR 0001 — Agents start from existing ones and are trialled before being kept

## Status

Accepted (2026-11-25).

## Context

The repository is to offer agents for several professions. Public collections already hold role
files for them, but the stars of a collection are not evidence about one of its agents, and a role
file may bring no gain over the generalist.

The only trial so far gave 32/32 to both a copied role file and the generalist, one run per arm, on
an earlier and unpublished version (`agents/trials/data/RESULTS.md`). It shows no gain; it does not
show that there is none.

Alternatives considered: write each agent from scratch; install a third-party plugin; use the
generalist for everything, with no trial.

## Decision

We start from an existing public agent: one file copied unmodified into `candidates/`, pinned to a
commit, with its licence, and read in full before any trial. No third-party plugin is installed for
a trial.

We compare it with the generalist on a need that exists, with invented data. The verdict is kept,
adapted or generalist, recorded in the `RESULTS.md` of the trial. Without a measured gain the agent
is not shipped and the generalist is the answer. A trial that both arms pass fully gives no verdict:
it is made harder first. A person takes the decision.

## Consequences

- No agent is added on reputation, and each one costs a trial: writing it, its model runs, its review.
- A role without a concrete need has no agent.
- A trial can be too easy or too narrow to tell the arms apart, and its published cases may be known
  to a model: a verdict holds for that trial and that model only.
- A copied file keeps its licence and its source, and does not follow its upstream by itself.
