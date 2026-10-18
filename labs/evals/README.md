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
3. Play the human turns in one headless `claude -p` session, resuming it for each
   turn after the first. User settings, plugins and MCP servers stay out.
4. Snapshot the vault before and after, then grade the **transcript** and the
   **vault diff**.
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

## Fixture vaults

Small, hand-written and synthetic. Each one is built to provoke one behaviour.
None contains real notes.

| Vault | Built to provoke |
|---|---|
| `band-or-pottery` | Orient: two hobbies competing for the only free evening, with lines worth quoting |

## Showing a case can fail

`mutants/` holds broken copies of the skill. Run one with `--skill`, and the case
it targets should print `FAIL`:

```
python3 labs/evals/run_evals.py --skill labs/evals/mutants/companion-paraphrase
```

## Adding a case

Add an object to `cases.json`: `id`, `vault`, `overlay` (Markdown, or null for a
vault with no Overlay), `turns`, `graders` (names from `graders.GRADERS`), and
optionally `"judge": true`. Write the grader test-first in `test_graders.py`,
including a mutant reply that must fail it.

Adapted from ae-daily-driver's `labs/evals`, with no dependency on that repo.
Fixture vaults take the place of its mock Jira MCP.
