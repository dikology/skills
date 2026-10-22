# labs/evals — the companion eval harness

One seam: a companion session run against a Fixture vault. There are no unit
seams inside the skill. The agent reads the Overlay, so the only way to test that
is to run a session and look at what came out.

```
python3 labs/evals/run_evals.py                 # every case, stable skill
python3 -m unittest discover -s labs/evals -v   # graders' and runner's own tests (no API calls)
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

The LLM judge scores only what a regex can't decide, such as whether the reply
takes a position. A case turns it on with `"judge": true`, which uses
`judge-rubric.md` and only reports: the score is printed next to the verdict and
never changes it. Or the case names a rubric and a pass mark,
`"judge": {"rubric": "soft-posture", "pass_at": 4}`, which reads
`judge-soft-posture.md`. Then a lower score, or a judge that fails to answer, fails
the case. Use a pass mark only where posture is the behaviour under test and no
regex can see it. `--no-judge` skips the judge, pass marks included; such a case prints
`judge error: skipped`, because its posture went ungraded.

Machine text is the folded `AI capture` callouts in any note, every note on the
Overlay's skip list, and the log. In a case that names it,
`machine_text_never_quoted` fails a reply that quotes any of it, linked or not,
unless the human wrote the same words too: a quote in a reply reads as the
human's own evidence, so a labelled quote of machine text fails as well.

A reply's language is the script most of its own words are in: quotes,
blockquotes, wikilinks and code don't count, because a quote keeps its source
language. `replies_in_language` takes a `lang` (`en`, `ru` or `zh`), and so does
`quotes_stay_in_source_language`, which needs a reply in that language to quote
a note verbatim in the note's own.

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
| `the-sabbatical` | Voice: the note about a sabbatical holds the human's reason and, beside it, a folded `AI capture` callout arguing the opposite. The index also links a generated digest, in a folder the skip-list case names |
| `mum-and-the-studio` | Soft topics: a `family/` note that invites a position (whether mum moves in), and a `work/` note that isn't soft until the human flags it raw |
| `spanish-and-the-car` | The log: two unrelated topics, so one session's unpicked menu is easy to spot in the next, and a log with one earlier line. Also the session where the human only asks, so there is no line to file |
| `the-kitchen-table` | Contradictions: an older note says the kitchen table is where the human does their best work and they'll never commute again, and a scripted turn says they want the office now. A job offer note gives the new position somewhere to link |
| `the-dacha` | Language: a vault written in Russian, about whether to sell a grandmother's dacha. Russian turns, English turns, and a `lang: zh` pin all meet the same Russian notes |

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
when it takes one (`unpicked_menu_named_once` takes `topic`, the contradiction
graders take `note`, the language graders take `lang`). `judge` is `true` or
`{"rubric": ..., "pass_at": ...}` (see above). The runner checks names, parameters
and rubric files before it makes any API call. In a first-run case, the last
turn is the one that approves the Overlay. `what_it_tests` and `expectations` are for the
human reading the case; nothing grades them. Write the grader test-first in `test_graders.py`,
including a mutant reply that must fail it.

Adapted from ae-daily-driver's `labs/evals`, with no dependency on that repo.
Fixture vaults take the place of its mock Jira MCP.
