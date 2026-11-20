# Handoff — maintainer working note

**Not part of the shipped plugin.** This is a session handoff for whoever picks the work up next,
overwritten at each handoff; `README.md` is the user-facing entry point. Everything substantive lives in
the artifacts linked below — this file only points, per the `handoff` skill.

**Date:** 2026-11-20 · **Close of:** `ed4cc405` scored on both pinned language cases (313,630 tok, 2
case-runs), and the pointer door landed as the span audit's fourth number (0 tok) · **Branch:** `main`
**Next session is for:** score the who-spoke half on `ed4cc405` (`--arm candidate --case follows` ×2–3,
≈0.3M), then the promotion run, then the gate.

## Read these first — do not re-derive them

| What | Where |
|---|---|
| The run bar as amended, and why | #17 body → [issue #17](https://github.com/dikology/skills/issues/17); the gate argument in [comment 6691486468](https://github.com/dikology/skills/issues/17#issuecomment-6691486468); the draft clause I withdrew in [comment 6691743157](https://github.com/dikology/skills/issues/17#issuecomment-6691743157) |
| The rendering round and its measurement | commits `f29d156`, `2316007`, `3b9a98e`, `4d73da8`, `3c1c6e9`, `1a04d9a` + this one; narrative in `CHANGELOG.md`, `## [0.2.0]` |
| Term definitions (Mark, Span, Two-shape scan, Script test, Wrong door, **Pointer form, Pointer door**, Corpus, Overlay, Stable/Candidate) | `GLOSSARY.md` |
| The four numbers the audit reports, how each was checked against the gate, and what `pointer`'s denominator is | `labs/evals/README.md` → "The span audit" |
| Ticket history, per-copy verdicts, AC status | **#26 is CLOSED (COMPLETED) since 2026-11-20T06:06Z** — the maintainer closed it, no comment after the 11-06 one. Open: #17, #24, #25, #27, #28. No #29 exists |
| Every run's verdicts + the byte-string it scored | `labs/evals/results/<run>/summary.json` — gitignored, **the only copy**; archived as below |
| Evidence archive | `~/Downloads/evals-results-2026-11-06.tar.gz` (2,321 entries verified against the disk listing, 113 run dirs); earlier `…-2026-11-03.tar.gz`. **Re-archive: results/ is now 119 run dirs** |
| The 0-token sweeps behind the tables | Method, not files: `python3 labs/evals/span_audit.py results/<run> --skill companion --json` (needs `raw_decode` — the CLI prints prose after the JSON), summed by the tree-hash in `summary.json`, **skipping run dirs whose `summary.json` says `skill: improve`** (118 of the 119 are companion's; an improve dir exits 2) |

## State in seven lines

- `skills/companion` (Stable) = `e981bb4e`. **No promotion, no tag, no both-arm gate spent.** improve's
  arms are identical (`0e3cbd00f056`). HEAD was `1a04d9a` == `origin/main` when this round started — the
  four commits the last handoff called unpushed **are pushed**.
- `labs/companion` (Candidate) = **`ed4cc405`**, and it is **now measured**: `fix26n_pin1`
  (`lang-pin-zh`) PASS 1.00 at 231,801 tok / 118.0s, `fix26n_guard1` (`lang-quote-stays-source`) PASS
  1.00 at 81,829 tok / 30.9s — 2 case-runs, candidate arm only, `--case` filtered, one frozen hash
  verified before and after. Priced at ≈220K from saved medians before launch; landed 313,630, inside
  the 422K the saved maxima predict. **No other case has ever scored these bytes.**
- **Audit of those two runs:** 13 claim-bearing marks, **3 broken, 0 `claim-fail`**, 0 unowned, and
  **2 wrongdoor** — `продать её руки`, `от субботы остаётся вечер`, in the guard case's TENSION line, in
  a case the gate scores 1.00. The 3 broken are all one mechanism, the reply's own line wearing Marks:
  `出门的理由` (`self-quote`), `留不起`, `不想` (`no-source`). Scoped the same way across every saved run
  of these two cases: `6ad215ae` 3 of 34 (2 `claim-fail`), `518d33de` 3 of 28 (2 `claim-fail`,
  1 `no-source`), `ed4cc405` 3 of 13 (0 `claim-fail`).
- **The rendering count is clean on 13 marks, which is not the same as cured:** `b3e23878` also reports
  0 `claim-fail` on these two cases (of 24 marks), and review had already found two false claims in the
  note that praised it. What is new is that the *door* was counted being taken beside the clean number.
- **Proved used, at 0 tokens, by the new fourth number.** `ed4cc405`: **4 pointer forms — 3 bare,
  0 marked, 1 that filled nothing** (`是那条手`, where 那条 governs a noun). The three bare ones are the
  construction the `Language` sentence prints (`[[thursday evenings]] 记的是加一样就得卸一样`,
  `[[the band]] 记的是开车回家那一刻`). `518d33de` on the same two cases: 7 bare / 1 marked, and that 1
  *is* the `fix26m_lang2` loss (`那句「加一样就得卸一样」`). Two runs, so it is a lead.
- **The instrument landed.** `pointer_doors` in `span_audit.py` — the audit's fourth number
  (`bare`/`marked`/`weighed`/`other`), in the row, the CLI line and `--json`; 8 tests; harness
  **365 OK** (was 357); README + GLOSSARY name **Pointer form** / **Pointer door**. It counts a shape,
  grades nothing, changes no verdict, and the exit code is still only about `broken`.
- **The figure the rendering sentence was written from does not reproduce.** Over the corpus that note
  had (every saved companion arm-case except this round's two runs): **174 forms = 130 bare, 12 marked,
  16 weighed, 16 other**. Its **12 marks reproduce; its 151 "plain" do not**, and its 92.6% matches
  nothing — the honest ratio is **130 of 142 = 91.5%**, denominator = bare+Marks, printed by the CLI.
  The conclusion (bare is already the model's habit; 17 of the 24 byte-strings that write the form write
  it with 0 marked) stands; the arithmetic in `CHANGELOG.md` at `1a04d9a` does not. `lang-pin-zh` is
  still a coin — 0.76 PASS/run pooled over 16 byte-strings, and `ed4cc405` is 1 of 1 on it.

## Decision pending from the maintainer (this blocks the release)

One both-arm run of **26 cases / 52 rows** (companion 21 + improve 5) on post-promotion bytes ≈ **12M tokens**; companion-only 21×2 ≈ **9.7M** is the promotion evidence. Prior spend for scale: `gate_companion_v6` 9.70M, `gate26_both` 9.27M. Gate odds are already computed in #17's comments — read them before recomputing.

- **`--promote` is still blocked on a run, not on prose.** Every run of `ed4cc405` used `--case`, which
  the promotion guard refuses by design. The promotion evidence is one unfiltered `--arm both`
  companion run (≈9.7M).
- **#17's 0-broken clause still needs a full-set candidate arm at 0 broken.** The best full-set
  measurement on record remains `fix26l_sweep1` (`6ad215ae`): 20/21 PASS, 5,463,637 tok, **3 broken of
  127**, 1 unowned, 5 wrong-door. The two filtered runs above report 3 broken of 13 and are not that bar.
- **#26's closure is not this round's to reopen.** The tracker says COMPLETED as of 2026-11-20; these
  bytes still write 3 broken marks in the family that ticket named. That is recorded in
  `CHANGELOG.md`; commenting, closing or reopening issues stays with the maintainer.

## If the next session is a prose round, start here

- **The residue is the who-spoke family, and it is scoped.** `ed4cc405` carries both paragraphs (the
  who-spoke one from `518d33de`, the noun-slot one added since) and left 3 broken of 13 marks, all of
  them "the reply's own line wearing Marks". The case where that mechanism showed up invisible before —
  `lang-follows-human`, 2 `human-edited` marks in `fix26m_lang1` — **has never run against these bytes**.
  Cheapest probe: `--arm candidate --case follows` ×2–3 (≈0.3M). For #26's own AC 2 the price was
  **9 case-runs ≈1.63M** (`--case lang` = 4 cases ×2, plus `--case reversal` ×1), not the ≈0.9M one pass
  of four costs.
- **Check the sibling grader before writing "say it unmarked".** `framing_named`
  (`graders.py:821-847`) *fails* a framing held in Marks and passes only the one held in `code`. A
  who-spoke clause with no scope guard competes with #27's graded shape — the defect class that made
  `26c99207` unshippable. The paragraph already in the file ends by moving nothing a note or the human
  spoke; **do not trim that clause as redundant.** The `pointer` number cannot see that collision: it
  counts doors, and `weighed` is the door #27 rewards.
- **What the trigger is, pooled over every saved run** (unchanged, and untested against these bytes):
  the reply naming what the human really wants sits in front of the model's own Spans **20.5%** of the
  time when they wear Marks and **1.4%** when they take `code` (161 vs 881 — a kind-filtered sample, not
  a matched control; read the caveats in the `CHANGELOG.md` voice-round note).
- **#28's door is still open in a case that scores 1.00:** 2 wrong-door copies in the guard case's
  TENSION line, plus the sweep's 4-of-5 doors outside `lang-pin-zh` (one line repeats in
  `first-run-declined` and `no-log-no-writes`: `` `something else has to come off it` `` ←
  `[[thursday evenings]]`; also `` `Nobody says no and nobody writes anything` `` ← `[[the band]]`).
  Nothing was filed; #29 does not exist. 1 `unowned` from the sweep (`"I'd think about it"` in
  `raw-flag-softens`) is also still there.
- **Two moves that must not be repeated:** writing another forbidden surface form of the pointer
  sentence (eight byte-strings did that — mine the already-correct instances instead, and `pointer_doors`
  is now the committed way to do it at 0 tokens), and naming Marks at the composition site (printed
  corner-mark examples made corner marks *more* available). Add a third: quoting "151 / 92.6%" — it is
  corrected above, and the corrected figure has a denominator attached to it.

## Traps this round added

- **A check can pass for the wrong reason.** The first reading of the 151 was **139 + 12 = 151**, an
  identity that looked like exactly the reproduction the README demands. It was two accidents: the walk
  had no length floor (6 single-character nouns like `是那条手` counted bare) and this round's own 3 bare
  forms had already joined the corpus. Reproduce against the corpus the claim was made from, name the
  definition, and print the denominator.
- **A published aggregate can be self-inconsistent and still point the right way.** 12 marks reproduced;
  151 did not. Correct the arithmetic, and leave the decision it supported alone unless the corrected
  number argues differently.
- **The `.qwen/tmp` script left behind is not the script that made the number.** That probe now prints
  2 bare vs 31 marked — neither figure is the published pair. Any number meant to survive a session goes
  into `span_audit.py` with a test, not into a one-session probe.
- **Detail strings are claims.** The first `other` branch said "the note's characters left unmarked"
  without reading the Corpus; the review axis caught it. A classifier that names an owner must call
  `VaultView.holders`, the way `wrong_doors` does.
- **Tracker and remote state move between sessions.** `main` == `origin/main` (the last handoff's "4
  unpushed commits" are pushed) and #26 is closed. Read `git status -sb` and `gh issue list` before
  restating either.
- **`--case <full case id>` runs one case; `--case lang` runs four.** These two runs were deliberately
  separate so the guard case sat beside the loser. Filtered runs can never promote, whatever they show.
- **Say which denominator before comparing rates.** 3 broken of 13 marks (2 runs) is neither better nor
  worse than 3 of 28 (4 runs) without the case split beside it.
- **`span_audit.py results/<run>` on an improve run dir exits 2** ("no transcripts for companion") —
  group by `summary.json`'s `skill` field, not by the presence of a directory.

## Traps that cost tokens in earlier rounds (still live)

- **Freeze the arm before measuring.** The runner installs the skill per case, so editing
  `labs/companion` mid-chain means each run scores different bytes. `summary.json`'s tree-hash is the
  truth, and `--promote` refuses an arm edited after its run.
- **Do not launch runs with `nohup … &` inside a background shell** — the wrapper exits at once and no
  completion notification fires. Run the harness as a plain background command.
- **Chain eval runs with `;`, never `&&`.** `run_evals.py` returns 1 when any case fails; a FAIL is a
  result, not a crash.
- **Recompute every aggregate from `summary.json` in the same session**, and re-derive every trend or
  superlative in the order it needs before publishing it.
- **`grep_search` can answer "No matches" for text that exists here** — confirm with a direct read.
- Prove things by re-scoring saved transcripts (0 tokens), not by re-running: `results/` is gitignored
  and is the only copy.
- **Three tickets still write "20 cases"** (#24, #25, #26 — the last one closed) while
  `cases/companion.json` holds 21, and `CHANGELOG.md` line 19 plus #17's 11-03 line carry a stale
  "closed on evidence" claim. Deliberately not edited: rewording those lines is the maintainer's call.

## Suggested skills for the next agent

- **`tdd`** — any change to `graders.py` / `span_audit.py` goes test-first in `test_graders.py` /
  `test_span_audit.py`, with a reply that must fail it; the README requires this of a new classifier.
- **`code-review`** — the two-axis review is what caught both false claims last round and three this
  one; run it against the previous commit **before** the findings are written into the record.
- **`diagnosing-bugs`** — if chasing the who-spoke family or the wrong-door split instead of re-rolling
  prose.
- **`domain-modeling`** — before coining any new term. `Pointer form` and `Pointer door` landed this
  round, glossed in plain words; the repo's convention is that a coined name is not usable until it is.
- **`research`** — only if a primary source is genuinely needed; this repo's questions are answered by
  its own saved transcripts.
- Also: **`implement`** with a ticket ref, and **`triage`** if the English doors finally get filed.

**Nothing outward without the maintainer's explicit go-ahead** — GitHub comments/closes, pushes,
`--promote`, any both-arm gate. Single-arm candidate runs, with a token figure attached, are
pre-approved; the gate and promotion are not.
