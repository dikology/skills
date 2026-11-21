# Handoff — maintainer working note

**Not part of the shipped plugin.** This is a session handoff for whoever picks the work up next,
overwritten at each handoff; `README.md` is the user-facing entry point. Everything substantive lives in
the artifacts linked below — this file only points, per the `handoff` skill.

**Date:** 2026-11-21 · **Close of:** the maintainer's deliberate copy — `skills/companion` is now
`ed4cc405`, byte-identical to `labs/companion` and to the bytes `rel17_sweep2` scored (20/21 PASS,
5,708,528 tok). For the first time the measured copy is the shipping copy. · **Branch:** `main` ==
`origin/main` at `7f85ef9`, with the copy and this round's harness/docs work **uncommitted**.
**Next session is for:** the release note and #17's remaining boxes — CHANGELOG 0.2.0, the version in
both manifests, improve rows in both READMEs, ADR-0001's Overlay amendment, then tag and push. Nothing
is owed to improve's evals, and companion's full set plus the flip's three replays are spent.

## Read these first — do not re-derive them

| What | Where |
|---|---|
| **The bar changed, and why** | `docs/adr/0002-tickets-carry-evidence-releases-carry-criteria.md` — a ticket's closing criterion measures its own mechanism; a release's criteria are the release's own. The tag certifies "best-measured copy, defects named", not "every case green on one draw". |
| The nine terms this round coined | `GLOSSARY.md`: **Case, Draw, Flip, Regression, Shared flip, Gate, Shape-tight check, Broken rate, Closing criterion** — glossed in plain words, as the repo requires before a name is usable. |
| #17's history, incl. the 11-06 amendment that still governs the *span* half | [issue #17](https://github.com/dikology/skills/issues/17). **Its verdict half is superseded by ADR-0002 and is still unedited on GitHub — the tracker still reads "no case fails on both arms".** Replacement text was drafted in this round's session; pasting it is the maintainer's move. |
| What the shipping bytes measure | `labs/evals/results/rel17_sweep2/summary.json` — gitignored, the only copy. `ed4cc405`, 21 rows, unfiltered, judge on. Since 2026-11-21 those are **both arms' bytes**. The flip's evidence: `rel17_pin_r1`, `rel17_pin_r2`, `rel17_pin_r3`. |
| The four audit numbers on those bytes | `python3 labs/evals/span_audit.py labs/evals/results/rel17_sweep2 --skill companion --json` (needs `raw_decode` — the CLI prints prose after the JSON). 0 tokens. |
| improve's evidence | `gate_improve_shipped_v2`: 5 cases × 2 arms, **10/10 PASS**, on `0e3cbd00f056` — which is still both arms' hash today, a duplicate arm on identical bytes. **No new improve run is needed.** |
| Term definitions (Mark, Span, Two-shape scan, Script test, Wrong door, Pointer form/door, Corpus, Overlay, Stable/Candidate, Framing) | `GLOSSARY.md` |
| How a run works, and what each guard refuses | `labs/evals/README.md` |

## State in eight lines

- **Both copies are `ed4cc405` since 2026-11-21**, the maintainer's deliberate `rm -rf` + `cp -R`, not
  `--promote` — which was never run and would have refused this evidence anyway (a filtered or
  single-arm run cannot promote, and identical arms are "nothing to promote"). Measured across the whole
  set on those bytes: **20/21 PASS**, the single loss `lang-pin-zh` (`quotes_verbatim` on
  `"退不退"` credited to `[[the band]]`) at 0.80 / 153,644 tok. That case on these bytes: **4/5** —
  `rel17_pin_r1/r2/r3` each took it at 1.00 (151,379 / 151,929 / 153,607 tok, 456,915 total), so the
  failing Draw is named and shown passing 3 consecutive replays, which is what #17's flip clause asks.
- **The three replays certify the verdict, not the promise — audited free.** `rel17_pin_r1` 0 broken of
  6 marks, `r3` 0 of 6, but **`r2` passed at 1.00 while writing 1 broken mark** (`no-source`, invisible
  to the gate): 1 broken of 20 claim-bearing marks across the three, 0 unowned, 0 wrong-door. Three
  greens in a row is the release's evidence about the case, never about the quoting promise; keep the
  two denominators apart (the sweep's 5 of 120 is the promise number).
- **Audit of the swept bytes: 5 broken of 120 claim-bearing marks (4.2%), 3 unowned, 2 wrong-door, 5
  pointer forms — all 5 bare.** Only 1 of the 5 was graded by the gate; 4 were invisible to it. The
  comparison number is `fix26l_sweep1` (`6ad215ae`: 3 of 127 = 2.4%, 1 unowned, 5 wrong-door) — **the
  best rate on a copy carrying all three tickets' rules, not the lowest full-set number on record.**
  Re-auditing all 13 saved full-set arm-runs at 0 tokens, the lowest is `gate26_both`/candidate
  (`af3b94f0`) at **0 broken of 138 — with 16 wrong-door copies beside it**, the copy predating #27's
  shape, #28's door rule and #26's scan. Quote `6ad215ae` with that qualifier or a reader will think a
  cleaner copy exists; that pairing is why the 11-06 amendment retired "0 broken". `P(≥5 of 120 |
  2.4%) = 0.16`, so one Draw cannot separate a rise from spread — and the 4 ungraded ones are the
  **who-spoke family** #26 left as residue (`no-source` ×2 in `lang-follows-human-en`, ×2 in
  `log-one-line-per-session`), the same mechanism seen in English cases rather than a new one.
- **The candidate lost two cases to stable in the aborted both-arm run — say it plainly.** In
  `rel17_promote1`'s 9 shared cases, stable passed both and the candidate failed both:
  `framing-carried-over` FAIL 0.75 (hard `framing_named`, 79,442 tok, no session error) — by the term
  coined today, a **Regression** — and `unpicked-menu-resurfaces` FAIL 0.33 **with 0 tok and a session
  error**, which is a broken session, not a verdict on the copy. Stable's 19/21 (its own two losses:
  `line-handed-back`, `soft-topic-no-pushback`) stands; the two arms' losses did not overlap. **No
  tree-hash exists for either arm** — that run died before any summary was written — so it evidences
  shapes, not bytes.
- **The shipped copy does not teach what three checks grade.** `framing_named` (`graders.py:821`) passes
  only a framing in `code` on a line carrying no link; `skills/companion/SKILL.md` never says that (it
  says "Name the pattern" at `:70`, and "pointing back at your own citation needs no marks" at `:104`)
  while `labs/companion/SKILL.md:72-80` teaches the shape outright. Same asymmetry for #27's menu
  collision (`skills` `:37` against `:70`; resolved at `labs` `:38-40`) and #25's contradiction placement
  (`labs` `:235-236`, `:251-253`). **Every gate since #23 scored `labs/` while `skills/` kept the copy
  that still holds the defects** — which is the thing that looked like "the cases are too hard".
- **Two harness defects fixed, test-first; 370 tests OK** (was 365). (1) `summary.json` is written after
  every row through a side file and a rename (`save_summary`), so an interrupted run still says which
  bytes it scored and how far it got, and `promote()` refuses it by naming the skipped cases. (2) A judge
  whose reply holds nothing readable is asked once more; two broken asks no longer fail a case the hard
  graders passed — the row carries `judge_ungraded`, and both the report line and the comparison table
  print `judge ungraded: <arm>` so a skip cannot read as a pass.
- **Nothing outward happened.** No promote, no copy, no tag, no push, no issue comment/close/edit. #17,
  #24, #25, #27, #28 are untouched on GitHub; #26 stays closed as the maintainer left it.
- **The two-axis review earned its keep:** it caught a claim in an earlier draft of this note — "the
  candidate lost nothing to the shipped copy" — that the saved rows contradict (see the state line
  above), and it caught `labs/evals/README.md` still promising the old judge rule. Both are corrected
  here and in the README; run the review **before** writing the record, not after.
- Session spend: 7,025,221 eval tokens in the aborted both-arm run (`rel17_promote1`, 30 of 42 rows, no
  summary — it died under the old writer) + 5,708,528 in the sweep + 456,915 in the three replays =
  **13,190,664 eval tokens**, plus two non-eval reads (653,225 for the grader shapes against the skill
  text, and the review axes).

## If the next session is the release, start here

1. **Done 2026-11-21, by the maintainer:** `skills/companion` == `labs/companion` == `ed4cc405`, verified
   against `rel17_sweep2/summary.json`'s recorded hash. Commit `skills/` and `labs/` together with the
   sweep's table in the message, per `labs/evals/README.md`.
2. Then the release note: the **Broken rate** line in #17's shape with `unowned` and `wrongdoor` beside
   it, `lang-pin-zh` named with its draws on the shipping bytes (the three replays below), the who-spoke
   residue stated as residue, and improve's line citing `gate_improve_shipped_v2`.
3. Then #17's clause on GitHub — the tracker still carries the old bar, and a handoff is a pointer, not
   the authority.
4. Then the boxes #17 still owes that nobody has touched: CHANGELOG 0.2.0, version 0.2.0 in both
   manifests, improve rows in both READMEs, ADR-0001's one-line Overlay amendment, the generalized
   Overlay glossary entry, then tag and push.

## Traps this round added

- **Cancelling the tool call that is *waiting on* a background run kills the run.** The polling shell and
  the harness share a process group; one cancel cost 7.0M tokens and the whole summary. Wait in bounded
  slices and read the incremental `summary.json`, not the log.
- **A broken judge used to be a case failure.** Only `soft-topic-no-pushback` and `raw-flag-softens` could
  hit it (`pass_at: 3`). Both failed on stable in the aborted run with the judge scoring normally, so the
  old rule was not the cause there — but it did fire on the killed run's candidate `framing-carried-over`,
  beside a genuine `framing_named` hard fail. Do not read that row as "the judge hid a defect".
- **`--promote` now sees partial runs.** `latest_run` keys on mtime plus both arm names being present, and
  both names are registered before an arm's first row — so a killed two-arm run shadows the last complete
  one and `--promote` answers "didn't score <cases> in this run". Use `--promote <dir>` to name an older
  complete run.
- **`CHANGELOG.md` carries a one-character edit nobody in this session made:** line 7 reads
  `## \[0.2.0]`, which will print a literal backslash. Left alone as someone else's work.
- **Grading the shape the prose commands is not "cases too hard".** Tallies recomputed over **every
  `grade.json` under `results/` today — 124 run dirs, 439 arm-case rows, 57 grader failures, 52 failing
  rows** — `quotes_verbatim` 37 of them; `framing_named` 3 of 18 rows that ran it;
  `unpicked_menu_named_once` 4 of 29; `contradiction_surfaced` 6 of 56. Narrow, clustered, each cluster on
  a documented rule collision. Read them as teaching gaps before editing any check — and a literal
  `<functions>` tag inside a tool argument gets truncated by the parser, so escape the angle brackets in
  tests.
- **A published tally goes stale the moment a run lands.** An earlier draft of this note carried
  415 rows / 56 failures / 36 `quotes_verbatim`, true only *before* `rel17_sweep2` finished: the sweep
  added a row-per-case and one `quotes_verbatim` failure. State the corpus with the number, and
  recompute in the session that publishes it.
- **`tokens` in a row is the session's tokens; judge asks are spent and never counted.** That is why the
  sweep priced at 4,745,180 (per-case candidate medians, the corpus before it ran) and spent
  5,708,528 — ~20% under-read, before Q8 added a second ask. Price low and budget high until
  `run_case` counts what the judge cost.

## Traps that cost tokens in earlier rounds (still live)

- **Freeze the arm before measuring**: `summary.json`'s tree-hash is the truth, and `--promote` refuses an
  arm edited after its run.
- **No `nohup … &` inside a background shell** — run the harness as a plain background command.
- **Chain eval runs with `;`, never `&&`** — `run_evals.py` returns 1 when any case fails; a FAIL is a
  result, not a crash.
- **Recompute every aggregate from `summary.json` in the same session**, price every run before launching
  it (this round: 4,745,180 at per-case candidate medians, 6,258,812 worst case, 5,708,528 spent), and
  re-derive every trend or superlative before publishing it.
- **Prove things by re-scoring saved transcripts at 0 tokens** — `results/` is gitignored and is the only
  copy.
- **`grep_search` can answer "no matches" for text that exists here** — confirm with a direct read.
- **Three tickets still write "20 cases"** (#24, #25, and the closed #26) where `cases/companion.json`
  holds 21, and #17's 11-03 paragraph still reads "#23, #24, #25 and #26 are all closed on skill-text
  fixes". ADR-0002 says who fixes those lines: the maintainer, on the tracker.
- **Python is 3.9 here** — no nested f-strings with same-type quotes, and `str | None` only survives
  because of `from __future__ import annotations`.

## Suggested skills for the next agent

- **`grill-with-docs`** (user store) — one round of it found the untaught-shape defect that six rounds of
  running gates did not; the frontier method is cheaper than a Draw.
- **`tdd`** — both harness changes went red→green in `test_run_evals.py`; a new classifier still owes that
  in `test_span_audit.py`.
- **`code-review`** — run it against the previous commit *before* findings go into the record.
- **`domain-modeling`** — before coining any term. Nine landed this round.

**Nothing outward without the maintainer's explicit go-ahead** — GitHub comments/closes/edits, pushes,
`--promote`, the `labs/` → `skills/` copy, any tag. Single-arm candidate runs, priced before launch and
capped near 5M a session, are the agreed way to buy evidence.
