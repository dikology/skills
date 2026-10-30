# labs/evals — the Library's eval harness

One seam: a skill session run against a Fixture vault. There are no unit
seams inside a skill. The agent reads the Overlay, so the only way to test that
is to run a session and look at what came out.

```
python3 labs/evals/run_evals.py                         # companion, every case, stable arm
python3 labs/evals/run_evals.py <skill>                 # any Library skill, by name
python3 labs/evals/run_evals.py <skill> --arm both      # stable and candidate, compared case by case
python3 labs/evals/run_evals.py <skill> --promote       # candidate -> stable, if it lost nothing
python3 -m unittest discover -s labs/evals -v           # graders' and runner's own tests (no API calls)
```

## Running a skill by name

The skill's name is the first argument; with none, it is `companion`, so every
command below without a name runs companion. The name decides three things:

- **The arms**: Stable is `skills/<skill>/`, Candidate is `labs/<skill>/`.
- **The cases**: `cases/<skill>.json`, the skill's own case set. A name with no
  case set is a setup error.
- **The install path**: the skill is copied into each temp vault as
  `.qwen/skills/<skill>/`, so `/<skill>` invokes it — the folder qwen looks for,
  which is not the folder the plugin ships into. That holds for `--skill`
  too: a mutant folder is installed under the skill's name, not its own.

A run saved before the harness took a name counts as a companion run.

Put the name before `--promote`: `--promote <dir>` takes a results directory,
so `--promote improve` would read `improve` as one.

Fixture vaults, graders and judge rubrics are shared; a case names the ones it uses.

Requires `qwen` on PATH, and a qwen that can reach a model with its own settings —
the run seeds an isolated `QWEN_HOME` from those settings and nothing else. Python
3.9+, standard library only.

## The loop: edit the candidate, compare, promote

Every skill has two copies. **Stable**, `skills/<skill>/`, is what the
plugin ships; it changes only by promotion. **Candidate**, `labs/<skill>/`, is the
one you edit; nobody installs it. A cycle starts with the two byte-identical.

1. **Edit** `labs/<skill>/SKILL.md`. Iterate on the cases it touches with
   `--arm candidate --case <id>`; that run is cheap and proves nothing on its own.
2. **Compare.** `--arm both` scores both arms on every case and prints one line per
   case: each arm's verdict and score, and the difference, candidate minus stable.
   A case is **LOST** when the candidate fails where stable passes, scores lower, or
   didn't run. Sessions are probabilistic, so a single loss can be noise: run again
   before you decide the edit is wrong.
3. **Promote.** `<skill> --promote` reads the newest saved run of both arms of that
   skill (or `--promote <results dir>`) and copies its candidate over its stable;
   no other skill is touched. It refuses, and
   changes nothing, when that run was made by another agent, scored another skill or one
   arm only, used `--case` or `--no-judge`, skipped a case in `cases/<skill>.json`, or the
   candidate lost any case; or when either arm has been edited
   since the run (each arm's files are hashed into `summary.json`). After a promote
   the two copies are identical again, so the next cycle starts clean.

Promotion is justified by the run, not by reading the diff. Commit `skills/` and
`labs/` together, with the run's comparison table in the message. Following
ae-daily-driver's ADR-0003.

## What a run does

For each case in `cases/<skill>.json`:

1. Copy `fixtures/vaults/<vault>/` to a temp directory and append the case's
   Overlay to its `CLAUDE.md`.
2. Install the skill under `.qwen/skills/<skill>/`, unmodified, the way a
   Consuming vault installs it.
3. Play each session's human turns in headless `qwen`, resuming the session
   for each turn after the first and starting fresh for the next session. Every
   turn runs against a `QWEN_HOME` the run made for itself, seeded with nothing
   but how to reach a model: user settings, hooks, extensions, user skills and
   MCP servers stay out, and auto-memory is switched off in that home whatever the
   developer keeps set — a turn that stops to write memories spends itself on the
   harness instead of the vault, and one case would remember its way into the next.
   The vault's own Overlay and installed skill are still
   read. Your own environment still reaches the turn, because that is one way the
   login arrives. A turn that loaded an MCP server anyway, reported no session
   setup, never invoked the skill, or answered as a different session than the one
   it was told to resume, fails the case — a reply that merely looks like the
   skill is not evidence.
4. Snapshot the vault before the first turn and after every turn, then grade the
   **transcript**, the **vault diff** and, where order matters (first-run setup,
   one log line per session), the snapshots between turns.
5. Print one `PASS`/`FAIL` line per case and keep, under `results/<timestamp>/<arm>/<case>/`:
   `transcript.md`, `transcript.json`, `vault.diff`, `grade.json`. `grade.json`
   records the session ids, the tokens the case spent (qwen reports no price) and
   the skills it invoked. `summary.json`
   holds the skill's name, the agent that ran it, every arm's rows and the hash of
   the skill folder it scored.

A case whose attempt reached no model at all — qwen printed nothing and the case spent 0
tokens — is played once more, and its row says `attempts: 2` beside the error it
discarded. That attempt graded the pipe rather than the skill and left no evidence but
the human turn, so nothing is lost by replacing it. A turn that timed out, exited
non-zero, or ran and misbehaved is never retried: that verdict belongs to the case.

With `--arm both` the steps run once per arm, stable first, and a comparison table
follows. The runner exits 1 when any case fails in any arm.

## Graders and the judge

Graders (`graders.py`) look at what a user would see or find: the reply text and
the files in their vault. They never read the skill's prompt, and they never check
wording or section order. A case passes when every hard grader it names passes.

The LLM judge scores only what a regex can't decide, such as whether the reply
takes a position. It reads the transcript in its prompt and holds no tool that
touches a disk or a shell: plan mode, plus the exclusions listed in `DENIED_TOOLS`,
so it cannot edit the vault it is grading or go behind the transcript to look. A
case turns it on with `"judge": true`, which uses `judge-rubric.md` and only
reports: the score is printed next to the verdict and never changes it. Or the
case names a rubric and a pass mark,
`"judge": {"rubric": "soft-posture", "pass_at": 3}`, which reads
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

Improve's graders read the `## Improve` Overlay. The improved note is the
`[[link]]` in the first human turn, and the approval is the second.
`only_approved_moves_applied` reads the numbered moves from the diagnosis and
the numbers, range, `all` or `none` from the approval. It fails a diagnosis turn
that writes, and a change to any file other than the note, the log, a note an
approved move links, or the index when an approved move names it.
`prose_verbatim` fails when a line of the note is missing afterwards. Headings and
new lines may go around a line, `[[ ]]` around a word and an HTML-comment marker
after a claim, but an `AI capture` callout must stay byte-identical.

An Overlay field is read the way a user writes it: one line may set several
fields (`index, log, skip list: …`), and a value of "as in `## Companion`" is read
from that section. `fallbacks_named` fails a first reply that leaves an unset
`## Improve` field without its fallback (a clause that labels the field unset,
`log: none`, or names the field and its fallback together), one that calls a
field the Overlay sets unset, and a later reply that lists two or more of them
again. `no_maturity_ladder`, for a vault with no maturity field, fails a listed
move that promotes or sets maturity, deferred or not, a MATURITY section or a
line reading the note's level, and a change to its maturity. For "improve
<folder>", `candidates_listed` wants the first reply to name two or more of the
folder's notes and ask a question, with no more than one numbered list and at
most 25 lines: a list, not a diagnosis of each.

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
| `the-starter` | Improve: a sourdough `starter` note with visible gaps (no Definition, a term with no note of its own, a term never explained, an unsourced claim, a paragraph that wants to be its own note), four inbound links from three notes, one through its alias, and no index entry. A folded `AI capture` callout holds an unsourced claim that is not the human's. A schema file and a log with one earlier line, so a diagnosis that writes anything shows up in the diff, and an approval shows exactly which files its moves touched. Run with no Overlay, the same log and schema sit there unconfigured, as decoys. Two notes live in `bakes/`, for a folder request |

## Showing a case can fail

`mutants/` holds broken copies of the skill. Run one with `--skill`, and the case
it targets should print `FAIL`:

```
python3 labs/evals/run_evals.py --skill labs/evals/mutants/companion-paraphrase
python3 labs/evals/run_evals.py improve --skill labs/evals/mutants/improve-writes-before-approval
python3 labs/evals/run_evals.py improve --skill labs/evals/mutants/improve-rewrites-prose
```

## Adding a case

Add an object to the skill's `cases/<skill>.json` (a new skill starts a new file,
`{"skill_name": "<skill>", "cases": [...]}`; `skill_name` may be left out, but when
present it must match the file name): `id`, `vault`, `overlay` (Markdown, or null for a
vault with no Overlay), either `turns` (one session) or `sessions` (a list of turn
lists, each a fresh session), `graders`, and optionally `"judge": true`. A grader is
named as a string from `graders.GRADERS`, or as `{"name": ..., <parameter>: ...}`
when it takes one (`unpicked_menu_named_once` takes `topic`, the contradiction
graders take `note`, the language graders take `lang`, `one_improve_log_line` takes `op`, `promote` and `split` for a vault that renames them). `judge` is `true` or
`{"rubric": ..., "pass_at": ...}` (see above). The runner checks names, parameters
and rubric files before it makes any API call. In a first-run case, the last
turn is the one that approves the Overlay. `what_it_tests` and `expectations` are for the
human reading the case; nothing grades them. Write the grader test-first in `test_graders.py`,
including a mutant reply that must fail it.

Adapted from ae-daily-driver's `labs/evals`, with no dependency on that repo.
Fixture vaults take the place of its mock Jira MCP.
