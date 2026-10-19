# labs/evals — the companion eval harness

One seam: a companion session run against a Fixture vault. There are no unit
seams inside the skill. The agent reads the Overlay, so the only way to test that
is to run a session and look at what came out.

```
python3 labs/evals/run_evals.py                 # every case, stable skill
python3 -m unittest discover -s labs/evals -v   # the graders' own tests (no API calls)
```

Requires `claude` on PATH. Python 3.9+, standard library only.

## What a run does

For each case in `cases.json`:

1. Copy `fixtures/vaults/<vault>/` to a temp directory and append the case's
   Overlay to its `CLAUDE.md`.
2. Install the skill under `.claude/skills/companion/`, unmodified, the way a
   Consuming vault installs it.
3. Play each session's human turns in headless `claude -p`, resuming the session
   for each turn after the first and starting fresh for the next session. User
   settings, plugins and MCP servers stay out.
4. Snapshot the vault before the first turn and after every turn, then grade the
   **transcript**, the **vault diff** and, where order matters (first-run setup,
   one log line per session), the snapshots between turns.
5. Print one `PASS`/`FAIL` line per case and keep, under `results/<timestamp>/<case>/`:
   `transcript.md`, `transcript.json`, `vault.diff`, `grade.json`.

The runner exits 1 when any case fails.

## Graders and the judge

Graders (`graders.py`) look at what a user would see or find: the reply text and
the files in their vault. They never read the skill's prompt, and they never check
wording or section order. A case passes when every hard grader it names passes.

The LLM judge (`judge-rubric.md`) scores only what a regex can't decide, such as
whether the reply takes a position. Its score is printed next to the verdict and
never changes it. Turn it off with `--no-judge`.

`no_transcript` is graded on every case, named or not: no file a session writes may
hold two or more of one session's human turns. A one-turn session can't be told apart
from a filed line that way, so those cases also grade `no_writes`.

## Fixture vaults

Small, hand-written and synthetic. Each one is built to provoke one behaviour.
None contains real notes.

| Vault | Built to provoke |
|---|---|
| `band-or-pottery` | Orient: two hobbies competing for the only free evening, with lines worth quoting. Also the vault with no Overlay, for first-run setup, and the one where the human refuses the take with a line worth filing |
| `lisbon-offer` | Orient from the index: the notes about a job offer never name the city; only the index does, and an unindexed note that does name it is a decoy |
| `spanish-and-the-car` | The log: two unrelated topics, so one session's unpicked menu is easy to spot in the next, and a log with one earlier line. Also the session where the human only asks, so there is no line to file |

## Showing a case can fail

`mutants/` holds broken copies of the skill. Run one with `--skill`, and the case
it targets should print `FAIL`:

```
python3 labs/evals/run_evals.py --skill labs/evals/mutants/companion-paraphrase
```

## Adding a case

Add an object to `cases.json`: `id`, `vault`, `overlay` (Markdown, or null for a
vault with no Overlay), either `turns` (one session) or `sessions` (a list of turn
lists, each a fresh session), `graders`, and optionally `"judge": true`. A grader is
named as a string from `graders.GRADERS`, or as `{"name": ..., <parameter>: ...}`
when it takes one (`unpicked_menu_named_once` takes `topic`). The runner checks
names and parameters before it makes any API call. In a first-run case, the last
turn is the one that approves the Overlay. `what_it_tests` and `expectations` are for the
human reading the case; nothing grades them. Write the grader test-first in `test_graders.py`,
including a mutant reply that must fail it.

Adapted from ae-daily-driver's `labs/evals`, with no dependency on that repo.
Fixture vaults take the place of its mock Jira MCP.
