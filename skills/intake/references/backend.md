# Backend analysis or change

## Look at (Phase 1)

- Trace the path: entrypoint (route, consumer, job) → handler → service → storage. Read the code, not the names.
- The contracts: OpenAPI or GraphQL schemas, event and message schemas, shared types.
- Migrations, config and feature flags, and the tests around the path.

## Claims to verify

- "Endpoint X does Y."
- "Field Z is unused", "safe to delete".
- "There is an N+1", "this query is slow".
- "The transaction covers Z."
- "Only service A calls this."

## Checks

- Grep the callers, including other repos, async consumers (queues, events, scheduled jobs) and generated clients.
- Run the targeted tests; reproduce a suspected bug with a command or a scratch script outside the repo. The failing test in the repo is Task 1 of the brief, after approval.
- For a reported bug: look for what would make it not one (guard, default, config, covering test, documented intent), then whether a real caller can reach the path.
- Logs and metrics, when they are available.
- `EXPLAIN` on a dev database for a query claim.
- A read-only `curl` on a local or dev environment for a behaviour claim.

## Done when

A command whose output proves it (a test run, a query plan, a response body), printed in the transcript.

## Pitfalls

- Trusting a function or field name over what the code does.
- Calling something unused before checking event subscribers and other repos' consumers.
- Contract drift: changing a payload without its schema, its consumers or a versioning step.
- Touching production: every check runs on a local or dev environment.
