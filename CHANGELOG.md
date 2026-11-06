# Changelog

All notable changes to this Library. Versions follow [semver](https://semver.org);
the Library stays on 0.x until companion has run about ten real sessions with no
workaround and its evals pass.

## [0.2.0] — in preparation, not tagged

#23 is fixed and promoted, so companion's case set now passes under qwen on the quoting
failures that held the release: `gate_companion_v5` scored the Candidate at 19/20 against
Stable's 13/20, losing no case, and `companion --promote` ran on that evidence. What is still
outstanding is the run that *follows* a promotion, so the numbers describe the bytes that ship
with both arms identical — `--promote` makes them identical, but gate_companion_v5 measured the
Candidate before it became Stable, and `lang-pin-zh` only passes on both arms once both arms are
the fixed copy. No `v0.2.0` tag exists yet. #17's run criterion was amended on 2026-11-03, because
three gates had been eaten by coin flips rather than by defects: the tag needs one full two-arm run of
both skills' case sets, on the bytes that ship, in which **no case fails on both arms**, and whose
candidate arm reports **0 broken spans** in the span audit — a single-arm loss is named here with the
replays that pass it. #23, #24 and #25 are closed on evidence. Two things stand against that bar now:
**#26**, whose shape brought `lang-pin-zh` from 2 fails in 4 runs to 1 in 3 but has not met its own
three-consecutive criterion — its pointer sentence has been re-written by every round, and the runs keep
finding a new surface form of it — and **#27**, whose rule
collision is fixed in the candidate — `fix27b_fram1`–`fix27b_unp3`: 6 of 6 PASS, the framing named in
3 of 3 replies, `unpicked-menu-resurfaces` 3 of 3 with the menu named once — but not promoted, because
its last criterion is a both-arm run that has not been spent. companion's case set is 21 since #27's
`framing-carried-over` was added. #26's door-sort is the one measured gain of the round — on
`26c99207` it held **0 spans broken invisibly across 28 marks** (`fix26e_*`) — but that copy carried a
clause that bans #27's graded shape, and the collision-free copy that replaces it (`b36c3eba`) has not
reached that number: `lang-pin-zh` lost its single run on it with 2 broken of 8 (`fix26h_pin1`). No
copy since `af3b94` (`fix26b_*`: 3/3 PASS, 0 broken of 23) has met AC 3's three-consecutive bar, and
what still stands between this candidate and #17's 0-broken clause is the pointer sentence's rendering —
seen in a third surface form this round — which #28 says cannot be diagnosed until the instrument can
see the wrong door it is going through.

**#28's instrument landed, and the prose round it unlocked is measured but not closed.**
`span_audit.py` now reports a third number beside `broken` and `unowned`: `wrongdoor`, a `code` span
whose characters the Corpus holds — a copy that took the wrong door, which no grader reads because
marks copy and `code` weighs. AC 1 and AC 2 met at 0 tokens: the verdict on `fix26d_pin2` is the 5
derived by hand in the issue, and on `gate26_both` the classifier **adds 16 to the candidate arm
without moving its published 139 marks / 119 graded / 0 broken / 1 unowned** — which is the hole
shown open: that arm meets #17's 0-broken clause while 16 note lines sit where the clause cannot read.
- **Where the doors actually are, and the scope error that found.** Locating the exclusion by probing
  every saved code span (2,315 spans, 291 of them corpus-held, over the companion case sets) showed a
  span that is only a note's *name*, a `# heading` or a `[[link]]` is pointing at a note instead of
  copying its text — 143 of the 291. The Overlay-field vocabulary the issue asked to exclude needed no
  banned-string list: the Corpus is built without the Overlay, the skip list or an `AI capture`
  callout, so `lang: zh` and a digest line are simply not in it. Then splitting the 16 doors in
  `gate26_both` by case showed **12 of them in English replies, only 4 in `lang-pin-zh`** — so the
  first draft, written inside the `Language` paragraph, fixed a quarter of the number. The rule went
  where it belongs: `Pointing is not quoting`, whose clause *"even when its words are verbatim someone
  else's"* was itself the permission, narrowed to the human's own words; `Session shape`'s restatement
  narrowed the same way; `Language` now points back at it instead of restating it.
- **A false positive in the instrument, found by reading #27's case.** `framing-carried-over`'s
  `what I paid against what came back` is the **human's** own line and `framing_named` grades putting
  it in `code` — so `wrong_doors` reads the human's turns before the Corpus, as `_ungraded` already
  does. AC 1's 5 and AC 2's published numbers are unmoved by the fix, re-verified.
- **AC 3, the baseline the prose was written against** (1,135,759 tok): two candidate runs of
  `--case lang` on `b36c3eba`, hash-verified as the on-disk copy. `fix28_base1` passed **all four
  cases at 0 broken and 0 unowned while carrying 7 wrong-door copies** — the failure #28 predicts,
  caught by the instrument and invisible to the gate. With `fix26h_pin1` that is 5 doors over 3
  `lang-pin-zh` runs: **1.67/run**.
- **AC 4: met on the door number, not met on the bar.** On the final copy `8a965e9e`
  (`fix28_final_*`, all six hash-verified, 706,861 tok): **0.67 wrong-door per `lang-pin-zh` run**
  (2, 0, 0) against that 1.67 baseline, 1 door across the three English cases, and
  `framing-carried-over` clean at 0 doors with `framing_named` passing and the judge at 5/5 — so the
  widened rule did not re-open #27's collision. But the third run **failed `quotes_verbatim`** on
  `[[the band]] 那句"周四那个房间有人"` — a 中文 rendering inside marks, the pointer sentence #26 is
  still open on, not #28's mechanism. So *three consecutive runs at 0 broken* is **not met**, and by
  the old defect rather than the new one. Not promoted; `skills/companion` untouched; the both-arm
  gate unspent.
`fix28_v2_fram1` (superseded bytes) also passed on its hard graders with the judge erroring (`judge
error: no JSON in reply`, the judge's reply holding a `<identity>` role-setting block — treated as
noise, not as input).

`gate_companion_v6` (2026-11-01, 20 cases × 2 arms, qwen, judge on, 9,704,776 tokens) ran that
follow-up cycle and **did not promote: 37/40, candidate lost 2**. It also answered #24: on the
fixed Candidate the compound dated annotation occurred in **0 of 8 runs** — `fix11`–`fix16`, the
gate, and a replay — while the same grader failed 3 of 9 runs on the previous copy. Both losses
are other defects, each reproduced once and passing its replay, so neither is deterministic: the
Candidate's `reversal-annotated` failed `contradiction_surfaced` because the model asked the
three-way question inside the Orient reply and then pointed back at its own citation, leaving no
single reply holding the note's quote, the human's words and the question together; the
Candidate's `lang-pin-zh` failed `quotes_verbatim` on `[[thursday evenings]] 那句"必须有事从周四下来"`,
a 中文 rendering inside marks — the residue #23 recorded as a rate rather than a cure. The Stable
arm's only loss, `line-filed-under-target`, is a false FAIL: the model printed `NEXT MOVES` on
reply 1, which `thinking_turns()` reads as the close, so the pool emptied and a verbatim dated
filing was graded as "nothing under ## Lines I said is a whole sentence the human said" — proven
by re-scoring the saved transcript, 0 tokens. Three new blockers, no promotion, `skills/companion`
still `e981bb4e`, and the run that follows a promotion is still the thing the tag needs.

`gate25_candidate` (2026-11-01, candidate arm only, 20 cases, 5,315,417 tokens) closed #25 —
`contradiction_surfaced` 8/8 on `7526cd0` — and lost three more cases on one mechanism, filed as
**#26**. A span audit over the saved gates then showed how little of that mechanism the gate can
see: 13 broken marks in `gate25_candidate` where `quotes_verbatim` failed 3 of them, 44 in
`gate_companion_v5`/stable where it failed 10. #26 was therefore verified at the promise level, not
only by verdicts. `gate26_both` (2026-11-03, 20 cases × 2 arms, judge on, 9,271,120 tokens) **did not
promote: 39/40, candidate lost 1** — `unpicked-menu-resurfaces`, a collision between two older rules
and not the quoting mechanism, whose own reply is clean; the same case failed twice in three replays
on the *shipped* bytes, so the flip is not this change's. On the quoting axis the run is the
strongest evidence yet: the Candidate arm wrote 0 broken spans across all 20 cases while the Stable
arm broke the promise 8 times (5.4% of its marks) and passed all 20, its graders seeing none of the
8. No tag; `skills/companion` still `e981bb4e`.

### Added

- `improve` skill: a structural review of one note. It reads the note and the notes
  that link to it — by name or by alias — and replies with a diagnosis (STRUCTURE,
  CONTENT GAPS, SPLIT/MERGE, MATURITY, numbered ranked PROPOSED MOVES with `NOT YET`
  reasons, QUESTIONS) that changes no file. Only the moves approved by number are
  applied, the human's prose stays verbatim, skip-listed text is never touched, new
  stubs are capped at three per run, and promotion happens only when approved. The log
  takes one `improve` line per note per session, plus separate `promote` and `split`
  lines. Six `## Improve` Overlay fields, each with a fallback the skill names once:
  index, log, schema, maturity, verification marker, skip list. A field may point at
  another section ("as in `## Companion`"); a folder request gets a candidate list and
  "which one first?".
- `labs/improve/` — the Candidate copy, byte-identical to stable from the first
  release, so the edit → compare → promote loop works for improve too.
- Evals for improve: the `the-starter` Fixture vault, five cases
  (`diagnosis-writes-nothing`, `only-approved-moves-apply`, `no-overlay`,
  `overlay-points-at-companion`, `folder-lists-candidates`), graders `numbered_moves`,
  `only_approved_moves_applied`, `prose_verbatim`, `one_improve_log_line`,
  `fallbacks_named`, `no_maturity_ladder`, `candidates_listed`, and the mutants
  `improve-writes-before-approval` and `improve-rewrites-prose`.
- The `dikology` plugin ships both skills, so one install gives companion and improve.
  The plugin and marketplace descriptions are no longer companion-only.
- READMEs (EN and 中文): an improve row, its Overlay fields with their fallbacks, and
  an Overlay example showing both sections.
- companion: **the owner of a mark is named on the line the mark sits on** (#26, `labs/companion/`,
  scored on `gate26_both`). #23 made copying honest and #22 made the grader credit every note a line
  offers; what `gate25_candidate` lost three cases on, and `gate_companion_v6` one more, is neither —
  it is a mark whose words are right, or a rendering that is not, placed in the one sentence that has
  a link in its hand. The post-reversal wrap-up wrote
  `1. [[mornings]] is not reversed. "The train would eat the first hour of that." still stands …
  [[the hybrid offer]]` — a perfect copy claimed about a note that holds none of it, because the
  sentence that named its owner ended two words earlier; the pinned-language orient wrote
  `[[the band]] 里的立项理由就是"有个理由在周四出门"` — a 中文 rendering of an English line inside
  marks, on the line naming `[[the band]]`. The same replies carried clean quote lines that passed,
  so this was never copying discipline: it is where the copy is put.
  - New at promise level, **The owner is on the line**: a mark answers to a note named on the line the
    mark sits on, a sentence before it does not carry it, and the phrase with no owner on its line
    goes in `code`. The sentence that weighs two notes is named as the place it bites — comparing
    notes, saying what still stands after a reversal, re-pointing at a line quoted earlier — and given
    a shape instead of a prohibition: TENSION's, each note a link, the clash in your own words, any
    line you want back copied on a quote line of its own above. The reply that says what still stands
    after a reversal write repeats it, because that is where the model actually reaches for marks.
  - The pointer sentence in a pinned reply is named too — `[[дача]] 那句「…」` asks for the note's line
    and answers with your rendering — so the reading goes unmarked after the link or in the gloss
    `（注：…）`, which becomes the shape wherever a foreign line's content is weighed rather than the
    courtesy owed a reader who may not know the source. A phrase held up to be weighed goes in `code`
    like a word does, and 中文 has no exception: `该不该退乐队`, not 「该不该退乐队」.
  - Two habits the file had no sentence for: companion quoting **its own earlier reply** (added to the
    things with nothing to copy them from), and the human's words recalled slightly edited while their
    line is weighed against a note. The pre-send check binds on the line, not the reply: *each mark
    against the links on its own line, never against the paragraph's*.
  - Measured. First rate check, on the copy before the `code`-for-phrases clause was added
    (`fix26_lang1`, `fix26_lang2`, `fix26_rev1`: `--case lang` ×2 + `--case reversal` ×1): 9/9 PASS
    with 0 `quotes_verbatim` rejections — and the
    audit still found 1 broken span in the first run and 4 in the second, all of them the model's own
    中文 or Russian phrase wearing corner marks on a line naming no note. That residue is why the
    clause exists. AC 3 was met on those bytes: `lang-pin-zh` 3 consecutive runs and
    `reversal-annotated` 3 consecutive runs (`fix26b_*`), all 1.00, each with **0 broken and 0
    unowned** spans — against `audit25l1`'s 6 broken of 16 marks (1 graded) and `audit25r1`'s 2 of 10.
  - **Then the record moved, and it moved against this change.** The two sentences fixed after review
    were measured too (`fix26c_*`, three runs per case): `reversal-annotated` passed 3/3 with 0 broken
    spans, but `lang-pin-zh` passed 2 of 3 — the third failed `quotes_verbatim` on four 中文
    renderings wearing 「」 on lines that name notes, `「减一样换一样」` and `「为了周四出门才加入」` beside
    `[[the band]]`, `「万一以后要用」` beside `[[thursday evenings]]`, and a one-character `「人」` the
    grader credits to both — 8 broken of 20 marks in the audit. So AC 3's three-consecutive bar is
    **not met by the copy as it now stands**, and #26 stays open: the shape took this case from
    2 fails in 4 runs to 1 in 3, which is a rate, not the cure its acceptance criteria ask for. The
    pointer sentence named one form (`那句「…」`) and the run wrote another (`唯一写明「…」的笔记`); that
    form is named too now, with the #27 collision fix beside it.
  - AC 3 a third time, on the bytes that also carry #27's fix (`fix27_*`, 9 runs): **9/9 PASS**, and
    `quotes_verbatim` clean in all six pinned/reversal runs — the case-level half is met at last. The
    audit is not satisfied: three broken spans remain, all of them the model's own words wearing
    corner marks on lines naming no note — `「人」` and `「没有」` (one character each) and
    `「陶艺填同一个位置」`, in `fix27_pin2` and `fix27_pin3`. AC 3 asks for 0 broken *graded or not*, so
    #26 stays open on the invisible half even though the mechanism that loses cases is gone: the
    single run that failed for the visible reason (`fix26c_pin3`) is not repeated, and the residue is
    now the 中文 emphasis habit at one-character scale, which no grader has ever seen.
  - **AC 3 a fourth time, and the axis that moved.** Three copies measured back to back, each on its own
    hash. `d18cf243` — the 中文 shape naming `code` as the home for a weighed word, re-rendering the three
    rejected spans in their legal form inside one ordinary line — held `lang-pin-zh` verdicts at 3/3 PASS
    with 0 `quotes_verbatim` rejections, but not the audit: **3 broken of 27 marks** (`fix26d_lang1`,
    `fix26d_pin2`, `fix26d_pin3`; its other three language cases ran once in `fix26d_lang1` and were
    clean, 0 of 18). Reading those replies rather than their verdicts showed *why*: the model was using
    both homes backwards, parking the note's verbatim lines in `code` (`The drive home was the best part.`,
    `Nobody says no and nobody writes anything` — twice in one reply) while its own readings wore Marks
    (`"用退乐队换三小时"`, `"有人一起"`). So `Pointing is not quoting` became **Marks copy, `code` weighs**,
    with the two-word name minted for someone else's line listed among the things with nothing to copy it
    from. On `26c99207` (`fix26e_pin1`–`pin3`, `fix26e_unp1`): **0 spans broken invisibly across 28
    marks** — the first copy since `af3b94` (`fix26b_*`) to close the half that reopened the ticket, and
    the shape was seen firing rather than the topic failing to arise (`半具尸体`, `改了主意`,
    `我到底去过几次周四的 open studio` all went to `code`). It lost one case: `fix26e_pin1` failed
    `quotes_verbatim` on `你…担心的是"再也没人需要我出门"`. Across the fifteen `lang-pin-zh` runs of the five
    surviving copies (`fix26b_*`, `fix26c_*`, `fix27_pin*`, `fix26d_*`, `fix26e_*`) exactly two lost the
    case — `fix26c_pin3` and `fix26e_pin1` — and the pointer sentence has been written in three different
    surface forms across them (`那句「…」` → `唯一写明「…」的笔记` → `你…担心的是"X"`). AC 3's
    three-consecutive bar is therefore still met by no copy that also carries #27's fix.
  - **A fifth copy, and it was worse.** Adding a paste test to `A quote is a copy` — a Mark is a paste,
    or it is your reading — raised the audit to **8 broken of 32 marks** (`fix26f_pin1`–`pin3`,
    `82a6f43e`) and brought corner marks back (`「终于出门又回来了」`, `「不」`) after the sort had stopped
    them: naming Marks where the model composes prose makes Marks more available. The sentence was
    reverted.
  - **Caught in review, not in a run.** Both axes of the review of `26c99207` flagged the same new
    clause — *"no second copy at all when a quote line above already carried it; pointing back at your
    own citation needs neither marks nor code"* — and it was the worse of the two findings: it **bans the
    shape `framing_named` grades**. `fix27b_fram1` passes by quoting
    `- [[the evening class]] — "…what I paid against what came back."` and then holding that same phrase
    in `code` on the FRAMING line — a second copy, which is exactly what #27's case asks for. Left in,
    the clause put #27's measured case at risk in the gate that would score both, beside contradicting
    "Give a phrase you want again from a note quoted earlier its own line naming that note again" and the
    three-way exception in the sentence below it. Same failure class as #27's rule collision, found by
    reading the case rather than the copy. The clause is gone, the bans (`never `code` where…`) with it,
    and the handle stays owned in one paragraph only.
  - **Measured on the collision-free copies.** On `12957a85`: `lang-pin-zh` 2/3 PASS — `fix26g_pin1` 0
    broken of 8, `fix26g_pin2` 1 of 9, `fix26g_pin3` 3 of 10, the last failing `quotes_verbatim` on
    `"退乐队才能去 open studio"`. `reversal-annotated` — the other site the ticket's table names, and never
    run on a post-#27 copy before — PASSed with 0 broken of 7 and 1 `note-copy-unowned` (`fix26g_rev1`,
    615,410 tok). `framing-carried-over` failed 1 of 2 (`fix26g_fram2`): the reply held the test in
    `code` on the same line as `[[the evening class]]`, which is what #27's *own* bullet forbids ("the
    line holding the framing holds no link"), pulled open by part two of its three-part shape — what the
    test measures *there* names the note it came from. That is #27's collision and #27 is still open, so
    it is recorded here rather than patched from this ticket. Removing the clause that restated it gives
    `b36c3eba`, the copy committed: `framing-carried-over` 2/2 PASS at 0 broken (`fix26h_fram1`,
    `fix26h_fram2`, 120,662 tok), `lang-pin-zh` one run, FAILED, 2 broken of 8 (`fix26h_pin1`) — so the
    collision is gone and AC 3 is still not met.
  - **Round's cost and the honest verdict.** 3,752,611 eval tokens over 20 candidate case-runs across
    five byte-strings (`d18cf243`, `26c99207`, `82a6f43e`, `12957a85`, `b36c3eba`). The one durable
    result is the diagnosis, not the prose: the model reaches for Marks on what it is weighing because
    `code` is where it puts *the note's* English — and the copy that fixed that by fiat (`26c99207`,
    0 broken invisible of 28) did it with two bans, one of which collided with #27's graded shape. The
    best-measured copy for this case remains `af3b94` (`fix26b_*`: 3/3 PASS, 0 broken of 23 marks),
    which predates #27's framing fix and cannot carry it. Nothing is promoted; `skills/companion` is
    untouched; the both-arm gate stays unspent.
  - Filed as **#28**: a note's own line parked in `code` is invisible to `quotes_verbatim` *and* to
    `span_audit.py` (5 of 16 code spans in `fix26d_pin2` hold the Corpus's characters), so #17's
    0-broken clause can be met by a copy that moved content out of Marks without ever giving it a quote
    line. That hole is why the pointer-sentence flip keeps being re-rolled against prose instead of
    being diagnosed; the instrument comes before the next shape. Not fixed here — the guard against it
    was one of the clauses the review struck, so #26 does not smuggle #28's cure.
  - `gate26_both` (20 cases × 2 arms, judge on, 9,271,120 tokens): the Candidate arm wrote **0 broken
    spans in all 20 cases** (139 marks, 119 of them graded claims, every one verbatim) — with one
    `unowned` it does not count as broken: `skip-list-never-quoted`'s MY TAKE carried
    `[[sabbatical]]`'s true line in marks on a sentence naming no note, which breaks the Orient
    reply's own "MY TAKE … holds no marks" with a copy that happens to be honest. The Stable arm in
    the same run broke the promise 8 times (5.4% of its marks) and passed all 20 of its cases — its
    graders failed **none** of those 8, two of which copy the log's own words back as if a person had
    said them.
  - Two sentences in this change were wrong in the way they could be read, and were found by review
    rather than by a run: the human's-words cure said "name it with a link", which beside a mark is
    the one shape `quote_sources` charges to that note (now: copy their line above on its own line,
    and the arguing sentence holds no marks); and the gloss was said both to carry a foreign line's
    content wherever a sentence needs it and never to stand in place of a quote (now: it sits beside a
    copy, and never replaces the quote line a reply owes when it needs the line as evidence).
    `gate26_both` measured the bytes before these two fixes, so the next both-arm run is the one that
    describes what ships.
  - **Not promoted.** The run scored 39/40: the Candidate lost `unpicked-menu-resurfaces`
    (`unpicked_menu_named_once`, 0.67) on a reply that named the unpicked Spanish menu a second time
    while following an older Posture rule — *name the pattern when the human reuses a framing from
    another note that may not fit here*. That reply is clean on quoting: it names `[[spanish class]]`
    with a link, holds no marks, and puts the note's own phrase in `code`. Replaying the case three
    times per arm says the case is a coin flip on **both** copies: Stable failed it 2 of 3
    (`fix26_unp_s2`, `fix26_unp_s3`, both `named again in reply 2`) and the Candidate failed it 1 of 4
    counting the gate. The collision is in the skill's own rules and predates this change — but under
    the runner's loss rule, a flip on this case blocks promotion whichever arm it lands on.
    `skills/companion` stays `e981bb4e`.
- companion: **name the framing, not the note it came from** (#27, `labs/companion/`, measured on
  `fix27b_fram1`–`fix27b_unp3`). Two rules had been reading against each other: Posture's *name the
  pattern when the human reuses a framing from another note that may not fit here*, and the Close
  menu's *say the unpicked line once; don't return to it unless the human does*. Neither said what a
  pattern is called by, and the only two hands available were the framing or the other note — naming
  the note is exactly the topic the second rule says must not come back. `gate26_both`'s candidate
  reply took the note: `you're doing the same arithmetic in [[spanish class]] … It may not fit here`,
  clean on every quoting rule and failing `unpicked_menu_named_once`.
  - The first fix (`29cf8fc`, measured on `fix27_unp1`–`unp3`) passed the case 3 of 3 and took the
    move with it. It stated the collision as a prohibition — *leave the other note's topic unnamed* —
    and a reply that never names a framing satisfies a prohibition perfectly. Read out of those
    transcripts rather than their `grade.json`: 0 of 3 session-2 replies imported a cross-note
    comparison, against 2 of 3 on the bytes before. Nothing could tell *the ban worked* from *the ban
    won*, because no grader fails when the pattern is missing.
  - The copy is now shape-first, with one owner. Posture's bullet is **Name the framing** and gives the
    sentence three parts — the test in `code`, what it measures there, what this note asks instead —
    so naming has a form to take; the link is absent because the shape holds *your* phrase up to weigh,
    not because the bullet forbids twice. The unpicked-menu step keeps only its own promise (say it
    once) and points at that shape.
  - Evals: the hole closed with a new Fixture vault and case. `the-studio-and-the-class` puts the
    paid-against-returned arithmetic in one note's own line and makes the other note a decision about
    evenings with no money in it, so a reply naming that test is carrying it over, not finding it here.
    `framing-carried-over` has the human carry it unprompted, and `framing_named` (`test`, `from_note`)
    fails a reply that names no framing in `code` on a line linking no note — the half the collision
    case structurally cannot see. It grades the naming, not the arguing: a reply that copies the phrase
    up and weighs nothing still passes, and the judge only reports that, so this ticket's *read the
    replies, not just the verdicts* stays load-bearing.
  - Measured on one set of bytes (candidate `02323656…` in all six, `skills/companion` untouched). The
    framing case **3 of 3 PASS and named in 3 of 3** — each reply put `what I paid against what came
    back` in `code` and said what it measures and what the job asks instead.
    - AC 2, first half — met: `unpicked-menu-resurfaces` passed 3 consecutive runs
      (`fix27b_unp1`–`unp3`, 1.00 each), the menu named in session 2's reply 1 and gone by reply 2.
    - AC 2, second half — **not met by that case, and not met by any run of it**: 0 of 3 import a
      cross-note framing, because Posture's trigger needs the human to bring a test and that session's
      never does. The old bytes named one in 2 of 3 on their own initiative; the requirement is now
      carried by `framing-carried-over`, which is the instrument the ticket's comment asked for.
    - AC 3, first clause — met: no case scored worse than the shipped copy on the shape graders; all
      six ran 1.00 with `quotes_verbatim` clean. AC 3, second clause — **not met**: the span audit
      gives 0 broken in five runs and one in `fix27b_unp2`, `"fix or sell"`, the human's `fix the car
      or sell it` recalled edited on a line naming no note, invisible to the gate. That is #26's
      residue, not this mechanism's; #26 stays open, and so does #17's 0-broken bar.
    - AC 4 — not met, see below.
  - One failure was the harness's, found by reading the reply instead of the verdict. `fix27r_fram2`
    graded FAIL against an earlier draft that stripped fenced blocks — the reply had named its framing
    inside one, and the fence's own backticks were opening a span across the sentence. `CODE_SPAN` now
    refuses an edge touching another backtick, and the same run then failed for the real reason: it put
    `[[the evening class]]` on the framing line, the collision wearing this case's clothes. That reply
    is why the bullet says where the note's name may go — a quote line of its own — not only where it
    may not.
  - **Not promoted.** The six runs above are `--case` replays on one arm, which `--promote` refuses by
    design; this ticket's last criterion is a both-arm gate, unspent, and it will score #26's open copy
    in the same candidate.
- Evals: the span audit (`span_audit.py`). `quotes_verbatim` sees a mark only where its own line
  offers a `[[link]]`, so an arm-run can pass every case with the quoting promise broken on lines
  that name no note. The audit walks every marked span in a saved run's transcripts and asks, of each,
  whose words these are — reading the vault through the case's Overlay the way the graders do, so the
  log and the skip list are machine text and not notes. A graded mark is put to `quote_claim`
  unchanged, so the audit can be checked against the gate; an ungraded one is matched against the
  Corpus (`human_text`), the machine blocks (`machine_text`), the human's turns and the model's own
  earlier replies. It reports two numbers: **broken** — #26's definition, a real copy credited to a
  note that does not hold it, or marks that copy nothing at all (the model's own weighing phrase, its
  own earlier reply, the human's words recalled slightly edited, a line of machine text) — and
  **unowned**, a note's line in marks on a sentence naming no owner: true words, wrong place, which
  is the shape #26's rule binds on rather than a mark #26 calls broken. A span under the gate's
  `MIN_QUOTE_WORDS` floor is a label and leaves the denominator, except where the script writes no
  spaces: 中文 counts by character, because a 中文 span is graded by the gate and never exempted by a
  whitespace floor. It costs 0 tokens, changes no verdict, and exits 1 on any broken span. Its graded
  bucket reproduces `quotes_verbatim`'s verdict on every arm-case of the six runs audited so far, and
  finds what they missed: 13 broken marks in `gate25_candidate` where the gate failed 3, and 44 in
  `gate_companion_v5`/stable (21.3% of its marks) where its graders failed 10. `GLOSSARY.md` names
  Span and Span audit.

### Changed

- The eval harness takes a skill name — `run_evals.py <skill>` — which resolves that
  skill's arms (`skills/<skill>/`, `labs/<skill>/`), its case set
  (`cases/<skill>.json`) and its promotion. Companion's 20 cases moved unchanged from
  `cases.json` into `cases/companion.json`.
- The harness drives `qwen`, not `claude`. The skill installs where qwen actually
  discovers it (`.qwen/skills/`), a run that never invoked the skill or that loaded an
  MCP server fails instead of reading green, every turn runs against a `QWEN_HOME` the
  run made for itself, and a case reports the tokens it spent because qwen prices
  nothing.
- ADR-0001 amended: an Overlay is a section named after one skill
  (`## Companion`, `## Improve`), not one section per vault.
- Evals: a run's own `QWEN_HOME` now switches auto-memory off, whatever the developer
  keeps set. Auto-memory is on by default, and a turn that stops to write memories
  spends itself on the harness instead of the vault — and one case remembers its way
  into the next. The path with no `settings.json` to seed from (a credentials-file
  login) is seeded the same way; it used to inherit the default.
- Evals: a case whose attempt reached no model at all (qwen printed nothing, 0 tokens) is
  replayed once and recorded as `attempts: 2`, because that attempt graded the pipe and
  not the skill. A turn that timed out, exited non-zero, or ran and misbehaved is never
  retried.
- Evals: `quotes_verbatim` reads a quote as a claim about every note the line offers as
  its source, not about the nearest link. A fragment passes when any offered note holds
  it verbatim and the failure names only the notes it could not find it in; a wrapped
  paragraph is the one line its reader sees; and words the human said in the session are
  handed back to them, not claimed about a note. Re-grading the saved `gate_companion_v3`
  and `gate_companion_v2` transcripts flips the two artifact failures
  (`contradiction-typed`/candidate, `first-run-approved`/candidate) and no other verdict;
  the truncated, translated and scare-quote failures are #23's, and still fail.
- improve: three rules were strengthened after the first qwen gate run broke each of
  them — a missing `maturity` field is dropped rather than read off the note's own
  frontmatter, a structure edit moves a whole line and never a sentence carved out of
  one, and one note gets one `improve` log line per session however many moves were
  applied. Each was promoted on a two-arm run where the candidate lost no case.
- companion: **a quote is a copy, not a recollection** (#23, promoted on `gate_companion_v5`).
  The Candidate already said quotation marks promise a note's exact words and still lost cases
  under qwen, so the promise is now a shape plus two tests the model can actually run. Marks take
  one shape, the **quote line** — `- [[note]] — "the note's characters"` — one line, one source
  note, one span pasted out of it; a line naming a note says what *that* note says, so a mark and a
  link meet nowhere else in a reply (the Close menu's option lines excepted: there the link names
  where a line will land). **Pointing is not quoting**: a phrase held up to be weighed, named, or
  asked about is companion's object, not the note's evidence, so it goes in `code` even when its
  words are verbatim someone else's. And copying is byte-for-byte — capitals, punctuation, slips —
  in a reply and in anything written into a note, because a recomposed word (`slow` for `slower`),
  a dropped one, a comma added, or an emphasis marker inside the marks is a claim no note keeps.
  A reply that is not in the notes' language keeps its copies on quote lines and its prose free of
  marks: `“ ”` and `「 」` are the marks too, and a 中文 reading follows the quote as `（注：…）`,
  never in its place. Non-adjacent sentences of one note are joined with a bare `…`, not with
  brackets. A contradiction is asked, not decided: the reply that surfaces one carries the note's
  quote line, the human's words on a line naming no note, all three types, and the question; their
  new position is not a confirmation, naming the type is not permission to write, and the dated
  annotation keeps its `[[link]]` and copies their line as they typed it. Before sending, the
  reply is checked one line at a time. Measured across all 20 cases of both arms of
  `gate_companion_v4` and `gate_companion_v5`, marked spans that copy nothing fell from 59 and 56
  (Stable) to 7 and 24 (the two runs of the fixed copy) — a real drop, not a cure: what is left is
  one rhetorical habit, naming the human's own question in order to reframe it, on lines that name
  no note and so are invisible to `quotes_verbatim`.
- `labs/companion/` holds an **unscored Candidate edit** from the review of that promotion: the
  Close-menu exception was stranded from the pre-send check (which says a link and marks meet only
  on a quote line, while the menu's `[a]` and `[e]` lines pair them), so the check now names `[a]`
  as the exception and `[e]` proposes its open question in `code` — a string to type, not a quote,
  which is what the skill itself teaches. Also fixed: the Russian exemplar dropped the note's final
  period inside its own marks, in a file that says copying is byte-for-byte. `skills/companion/` is
  the copy `gate_companion_v5` measured; these lines ship in no release until a two-arm run of the
  Candidate loses nothing and is promoted.
- `labs/companion/` holds a second **unscored Candidate edit** (#24), against the one case still
  failing on the shipped bytes: `gate_companion_v5` scored `reversal-annotated` 0.75 because the
  dated reversal annotation was a compound line. The paragraph asked for "one dated line" that
  "links the note holding the new position" and said nothing about what may stand inside marks on
  it, so the model reached for the Close menu's `[a]` shape, quoted the *older* note's sentence,
  and glued the link on — and `quote_sources` credits every mark to the notes the same line offers,
  which here was only `[[the hybrid offer]]`, a note holding none of those words. The copy was
  exact; the line's shape is what failed. The annotation now has its own literal line,
  `- **YYYY-MM-DD** — reversal — [[<new position note>]]: <their words, exactly as typed>`, holding
  no marks, so there is no claim to mis-credit; `[a]` keeps its exception and the paragraph says
  the two shapes are not to be merged. What that costs, plainly: marks were the only place a grader
  could see the copy rule, so an unmarked line that re-cases or trims their words now passes every
  grader — the rule is prose, not a check. Measured on the filtered case (`--case reversal`, 1 case
  × 3 runs each): `base1`–`base3` on the pre-edit copy passed 3/3, so green alone proved nothing
  (6 PASS / 3 FAIL across the runs on record); `fix11`–`fix13` passed with the words unmarked but
  dropped the human's terminal period, and putting their sentence last instead of after an em-dash
  cured it — `fix14`–`fix16` passed 3/3, each writing one dated line, no marks, the turn copied
  byte for byte with its punctuation. Pinned at the grader seam in `test_graders.py` (the v5 line as
  a mutant that must fail, beside the template that must pass); no grader, fixture or mutant
  changed, and the case's `expectations` now describe the shape the skill prescribes.
  `skills/companion/` stays `e981bb4e`, the copy `gate_companion_v5` measured. Both unscored
  Candidate bullets above were scored together in `gate_companion_v6` and the Candidate lost two
  cases there, so nothing promoted: the annotation template did its job and the losses were
  elsewhere, both described in the release note above.
- The glossary at the repo root is now `GLOSSARY.md`, and a multi-context repo would use
  `GLOSSARY-MAP.md`, following the rename the upstream skills adopted on 2026-08-15.
  `AGENTS.md`, `docs/agents/domain.md` and both READMEs point at the new name, and
  `docs/agents/domain.md` is byte-identical to the refreshed
  `setup-matt-pocock-skills` template again. No skill text, case set or grader named the
  old file, so no shipped byte moved and no gate result changed.

The Library stays 0.x: the 1.0 gate is still about ten real-vault sessions that need no
workaround, with the evals passing.

## [0.1.1] — 2026-10-28

### Changed

- The plugin root is now `skills/`, not the repo root. An install copies only the
  stable skills folder and its manifest; it no longer carries `labs/`, `docs/` or the
  repo files (READMEs, glossary, changelog). The plugin manifest moved to
  `skills/.claude-plugin/plugin.json`; the marketplace manifest stays in the repo-root
  `.claude-plugin/`. Installs pinned at `#v0.1.0` keep the old layout.

## [0.1.0] — 2026-10-23

First release. This is 0.x: it stays 0.x until about ten real-vault sessions
need no workaround. Expect the Overlay contract to change before 1.0.0.

### Added

- `companion` skill: challenger-style thinking partner over an Obsidian vault.
  Reads an optional Overlay, names every missing field with its fallback, and runs
  chat-only when the vault has no notes.
- Claude Code marketplace `dikology-skills` with one plugin, `dikology`.
- `CONTEXT.md` glossary and ADR-0001, "Overlay, not fork".
- Eval harness in `labs/evals/`: runs companion unmodified against a Fixture
  vault, grades the transcript and the vault diff, and keeps both as results.
  First case: `orient-quotes-corpus`.
- First-run setup: with no Overlay, companion says so, asks for every field in
  one message, shows the section, and writes it only after an approving reply.
  Declining writes nothing and the session runs on vault search.
- The log takes its one line per session when the Close menu is shown, as
  `menu unpicked`, and that line is rewritten if the human picks. The next session
  names an unpicked menu once, before orient.
- Evals: multi-session cases, a vault snapshot after every turn, graders with
  parameters, and six cases for first-run setup, the index, and the log.
- `[a]` files the human's own line, verbatim and dated, under the filing target on
  the note the session was about. With no filing target it writes nothing and gives
  the line back in chat. With no line of the human's to file, `[a]` is left off the
  menu and the other options keep their letters.
- Evals: graders `line_filed_under_target`, `line_handed_back`, `file_option_absent`,
  and `no_transcript`, which runs on every case. Three cases for `[a]`.
- Voice: companion never quotes an `AI capture` callout, a skip-listed note or the
  log, even labelled as machine text. It quotes the human's writing around the
  callout and argues with a machine-written claim in its own words.
- Soft mode: a topic is soft when its notes sit in a soft-topic folder or carry a
  soft-topic tag. Orient still quotes the notes but drops TENSION and MY TAKE.
- Evals: graders `machine_text_never_quoted` and `quotes_human_beside_callout`; a
  judge rubric for soft posture that can decide a case with `pass_at`; Fixture
  vaults `the-sabbatical` and `mum-and-the-studio`; four cases for voice, soft
  topics and the raw flag; mutants `companion-no-voice-guard` and `companion-no-soft-mode`.
- Evals for contradictions: a Fixture vault with a planted contradiction, a case
  where both positions are quoted verbatim and the human is asked reversal, nuance
  or domain mismatch, and a case where a confirmed reversal annotates the older
  note with its original text intact (the vault diff is additions only).
  Mutant `companion-no-contradiction-guard`.
- Language: replies follow the human's language, not the notes'. A `lang` pin in the
  Overlay sets the reply language whatever the human writes in. Quotes, the filed
  line and note names stay in their source language; a gloss may follow a quote,
  never replace it.
- Evals for language: a Russian Fixture vault, `the-dacha`; graders
  `replies_in_language` and `quotes_stay_in_source_language`; four cases (Russian
  turns get Russian replies, English turns over Russian notes get English replies
  with Russian quotes, a `lang: zh` pin over English turns, a Russian quote in a
  中文 reply); mutants `companion-wrong-reply-language` and
  `companion-translates-quotes`. Quotes may sit in 「」 marks, and a quote is no
  longer credited to a wikilink in another sentence.
- Stable and Candidate: `labs/companion/` is a working copy of companion. The eval
  runner scores `--arm stable`, `candidate` or `both`, and prints a per-case
  difference. `--promote` copies the candidate over stable on the evidence of a
  saved two-arm run, and refuses when the candidate lost any case, the run was
  partial, or either arm changed since.
- README: the Overlay fields with their fallbacks, a pinned install, and a 中文
  README (`README.zh.md`).

### Changed

- Evals: a quote from a note may change the case of its first letter to fit its sentence;
  every other character must still match the note. A filed line stays exact.
- Evals: the soft-posture cases pass at judge score 3, not 4. A score of 3 is
  gentle in tone with one reply that still steers (a verdict, an argued opposite
  side, or a pointed "but your notes say"). Companion lands there about half the
  time; a session that challenges as usual still fails.

[0.1.1]: https://github.com/dikology/skills/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/dikology/skills/releases/tag/v0.1.0
