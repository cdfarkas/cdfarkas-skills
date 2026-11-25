# data trial: results

Method: each arm got the workspace built by `bench.py make` and did the three tasks of
`TASKS.md`: the generalist with no role file, the other with one role file. `bench.py grade`
scored both with hidden cases and no model in the loop.

**The version in this folder has not been run by any model.** The scores below come from an
earlier version, not published, with the same three tasks and checks on another invented
domain. The data changed, so they are **not comparable** with any future run here.

Run on 2026-11-25, one run per arm. Model: Opus; the exact model id was not recorded.
The raw outputs are not published, so the figures cannot be recomputed from this repository.

## Scores

| Measure | `agents/trials/data/candidates/privacy-engineer.md` | Generalist |
|---|---|---|
| Checks passed | 32/32 | 32/32 |
| Tokens | 175,895 | 163,009 |
| Duration | 808,959 ms | 881,947 ms |
| Lines of mask plus purge code | 842 | 883 |
| Human review minutes | not measured | not measured |
| Three runs per arm | not measured | not measured |

## What the arms got wrong

Nothing that the 32 checks could see, in either arm.

## Conclusion

The trial saturates: no gain is shown for the Privacy Engineer. The differences in tokens,
duration and code size come from one run per arm and prove nothing. Both stay available for a
future specific need; the role file stays a candidate and is not shipped. The trial must be
made harder before it is run again.

## Not measured

- Any run of the version in this folder.
- Three runs per arm, so no variance.
- Human review minutes.
- The quality of the result beyond the 32 checks.
