# Handoff — maintainer working note

**Not part of the shipped plugin.** This is a session handoff for whoever picks the work up next,
overwritten at each handoff; `README.md` is the user-facing entry point. Everything substantive lives in
the artifacts linked below — this file only points, per the `handoff` skill.

**Date:** 2026-11-07 · **Close of:** the voice round (0-token mining + one prose change, unmeasured) ·
**Branch:** `main`
**Next session is for:** measuring that change, then deciding and running the v0.2.0 gate.

## Read these first — do not re-derive them

| What | Where |
|---|---|
| The run bar as amended, and why | #17 body → [issue #17](https://github.com/dikology/skills/issues/17); the gate argument in [comment 6691486468](https://github.com/dikology/skills/issues/17#issuecomment-6691486468); the draft clause I withdrew in [comment 6691743157](https://github.com/dikology/skills/issues/17#issuecomment-6691743157) |
| The prose change and its measurement | commits `f29d156` (two-shape scan + script test) and `2316007` (review corrections + full sweep); narrative in `CHANGELOG.md`, `## [0.2.0]` |
| Term definitions (Mark, Span, Two-shape scan, Script test, Wrong door, Corpus, Overlay, Stable/Candidate) | `GLOSSARY.md` |
| Ticket history, per-copy verdicts, AC status | #26 (its comments), #27, #28 — all open |
| Harness behaviour, graders, the span audit | `labs/evals/README.md` |
| Every run's verdicts + the byte-string it scored | `labs/evals/results/<run>/summary.json` — gitignored, **the only copy**; archived as below |
| Evidence archive | `~/Downloads/evals-results-2026-11-06.tar.gz` (2,321 entries verified against the disk listing, 113 run dirs); earlier `…-2026-11-03.tar.gz` |
| The 0-token sweeps behind the tables | Method, not files: `python3 labs/evals/span_audit.py results/<run> --json` grouped by the tree-hash in `summary.json`. The ad-hoc scripts of this session sit in `.qwen/tmp/` and are not kept |

## State in five lines

- `skills/companion` (Stable) = `e981bb4e`. **No promotion, no tag, no both-arm gate spent.** improve's arms are identical (`0e3cbd00f056`).
- `labs/companion` (Candidate) = **`518d33de`**, which no eval has ever scored — it is `6ad215ae` plus the
  voice round's one paragraph in `Session shape` (review retired the first two drafts, `7457aac1` and
  `97bb5b6f`, before anything ran). `6ad215ae` carries #26's scan + script test **and** #27's framing shape
  and #28's door rule; `518d33de` carries all of that too.
- Last full-set measurement of the *measured* candidate (`fix26l_sweep1`, bytes `6ad215ae`) →
  **20/21 PASS, 5,463,637 tok**, audit **3 broken / 127 claim-bearing marks, 1 unowned, 5 wrong-door**.
  The one loss is the graded broken mark, and it is the same mechanism as the other two — not a rendering;
  see the voice-round note in `CHANGELOG.md`.
- Harness tests: `python3 -m unittest discover -s labs/evals` → 357 OK.
- #26's pinned case on the corrected bytes is **2/3**, not 3/3; the 3/3 belongs to `b3e23878`, which review showed contained two false claims. Pooled across 16 candidate byte-strings the pinned case passes **0.76 per run**, and 3 of 12 three-run copies go 3/3 where chance predicts 5.2 — so a streak certifies nothing on its own.

## Decision pending from the maintainer (this blocks the release)

One both-arm run of **26 cases / 52 rows** (companion 21 + improve 5) on post-promotion bytes ≈ **12M tokens**; companion-only 21×2 ≈ **9.7M** is the promotion evidence. Prior spend for scale: `gate_companion_v6` 9.70M, `gate26_both` 9.27M. Gate odds are already computed in #17's comments — read them before recomputing.

## If the next session is a prose round, start here

The instrument already located the residue, scoped per case at 0 tokens rather than from the ticket's framing:

- **4 of the sweep's 5 wrong-door copies are outside `lang-pin-zh`; 3 are in English replies.** One line repeats: `` `something else has to come off it` `` ← `[[thursday evenings]]` in **both** `first-run-declined` and `no-log-no-writes`; also `` `Nobody says no and nobody writes anything` `` ← `[[the band]]`.
- **All 3 of the sweep's broken marks are one mechanism: the reply's own line wearing Marks.** Two are
  invisible to `quotes_verbatim` and leak through different holes — `пользуюсь ли я этим`
  (`lang-follows-human`) is where the script test genuinely cannot reach (reply, Corpus and human turn all
  Russian); `有人等` (`lang-pin-zh`) is not, since its notes and its single human turn are English under a
  pinned 中文 reply, so the test names that Span and the model wrote it anyway, inside
  `真正让你周四出门的是…`. The third is the graded one and cost the case: `一年四次的抵达值不值二十四万加所有周六`
  in the Close menu's `[e]` line, which the same reply had just written as its own prose — *not* the
  rendering the previous release note called it. What the trigger is, pooled over every saved run: the reply
  naming what the human really wants sits in front of the model's own Spans 20.5% of the time when they wear
  Marks and 1.4% when they take `code` (161 vs 881 — a kind-filtered sample, not a matched control: read the
  caveats in the `CHANGELOG.md` voice-round note). `518d33de` writes the shape and has never been scored.
  Cheapest probe: `--arm candidate --case follows` ×2–3 (~0.3M). #26's AC 2 baseline is **9 case-runs**
  (`--case lang` matches 4 cases ×2, plus `--case reversal` ×1) ≈ **1.63M** priced from the sweep's own
  per-case tokens, not the ≈0.9M one pass costs.
- 1 `unowned`: `"I'd think about it"` in `raw-flag-softens`.

**Two moves that must not be repeated:** writing another forbidden surface form of the pointer sentence (eight byte-strings did that; the one durable win came from mining the model's already-correct instances — 88 of 98 `那句`-type clauses were already unmarked, that being `f29d156`'s count over the 98 run dirs then saved, and results/ now holds 113, so re-derive before quoting it), and naming Marks at the composition site (printed corner-mark examples made corner marks *more* available, not less).

## Traps this round added

- **A claim inherited from the last round's release note was false.** The previous note called the sweep's
  graded broken mark "a 中文 rendering of a Russian note's arithmetic"; reading the transcript shows the same
  reply wrote that phrase as its own prose one paragraph earlier. Both rounds published it without checking
  the bytes. Re-derive an inherited claim before repeating it, and name the run it came from.
- **Check the sibling grader before writing "say it unmarked".** `framing_named` (`graders.py:821-847`)
  *fails* a framing held in Marks and passes only the one in `code`. The voice round's first draft told the
  model to say its own line unmarked with no scope guard, which competes with #27's graded shape — the exact
  class of defect that made `26c99207` unshippable. The paragraph now ends by moving nothing a note or the
  human spoke; do not trim that clause as redundant.
- **`--case lang` is 4 cases, not one.** `run_evals.py` matches case ids *containing* the filter, so
  #26's AC 2 is nine case-runs (≈1.63M priced from saved per-case tokens), not the ≈0.9M its own Costs line
  gives for one pass of four.

## Traps that cost tokens this session

- **Freeze the arm before measuring.** The runner installs the skill per case, so editing `labs/companion` mid-chain means each run scores different bytes. Two chains died that way today. `summary.json`'s tree-hash is the truth, and `--promote` refuses an arm edited after its run.
- **Do not launch runs with `nohup … &` inside a background shell** — the wrapper exits at once, no completion notification fires, and you are left polling. Run the harness as a plain background command.
- **Re-derive every trend or superlative in the order it needs.** Two published claims were wrong: sorting an audit table by count and calling it a trend (in date order the broken counts are 20, 6, 19, 13, 4, 0, 3), and a "lowest door count" two earlier runs already beat.
- **Recompute every aggregate from `summary.json` in the same session** — hand-carried token totals have been wrong in pushed commits more than once, including this round's first draft.
- **`grep_search` can answer "No matches" for text that exists here** — confirm with a direct read before concluding absence.
- Prove things by re-scoring saved transcripts (0 tokens), not by re-running: `results/` is gitignored and is the only copy.
- **Three tickets still write "20 cases"** (#24, #25, #26) while `cases/companion.json` holds 21; and `CHANGELOG.md` line 19 plus #17's 11-03 line carry a stale "closed on evidence" claim — only #23 is closed, while #24, #25, #26, #27 and #28 are open. Both flagged on #17 and **deliberately not edited**: closing the issues versus rewording the line is the maintainer's call.

## Suggested skills for the next agent

- **`tdd`** — any change to `graders.py` / `span_audit.py` goes test-first in `test_graders.py` / `test_span_audit.py`, with a mutant reply that must fail it; the README requires this of a new classifier.
- **`code-review`** — the two-axis (Standards / Spec) review is what caught both false claims this session; run it against the previous commit before spending eval tokens on what it finds.
- **`diagnosing-bugs`** — if chasing the wrong-door split or the same-language blind spot instead of re-rolling prose.
- **`domain-modeling`** — before coining any new term; `GLOSSARY.md` is the repo's convention, and every coined name needs a plain gloss there.
- **`research`** — only if a primary source is genuinely needed; this repo's questions are answered by its own saved transcripts.
- Also: **`implement`** with a ticket ref (fetches the issue, runs the TDD → review → commit loop), and **`triage`** if the English-case doors get filed as #29.

**Nothing outward without the maintainer's explicit go-ahead** — GitHub comments/closes, pushes, `--promote`, any both-arm gate. Single-arm candidate runs, with a token figure attached, are pre-approved; the gate and promotion are not.
