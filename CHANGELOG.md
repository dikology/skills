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
the fixed copy. No `v0.2.0` tag exists yet; that is #17, and #23 was its last open blocker.

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
  - Measured. `--case lang` ×2 + `--case reversal` ×1 on the new copy: 9/9 PASS with 0
    `quotes_verbatim` rejections; on the bytes this replaces, `lang-pin-zh` failed 2 of its 4 runs and
    `gate25_candidate` lost `lang-follows-human`, `lang-quote-stays-source` and `reversal-annotated`
    the same way. AC 3: `lang-pin-zh` 3 consecutive runs and `reversal-annotated` 3 consecutive runs,
    all 1.00, each with **0 broken and 0 unowned** spans — against `audit25l1`'s 6 broken of 16 marks
    (1 graded) and `audit25r1`'s 2 of 10 on the shipped bytes. `gate26_both` (20 cases × 2 arms,
    judge on, 9,271,120 tokens): the Candidate arm wrote **0 broken spans in all 20 cases** (139 marks,
    119 of them graded claims, every one verbatim, 1 unowned) while the Stable arm in the same run
    broke the promise 8 times (5.4% of its marks) and passed all 20 of its cases — its graders failed
    **none** of those 8, two of which copy the log's own words back as if a person had said them.
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
