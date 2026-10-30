# Changelog

All notable changes to this Library. Versions follow [semver](https://semver.org);
the Library stays on 0.x until companion has run about ten real sessions with no
workaround and its evals pass.

## [0.2.0] — in preparation, not tagged

The release gate has not passed: companion's case set does not pass under qwen (#22,
#23), so no `v0.2.0` tag exists yet and the pin examples in the READMEs stay on
`v0.1.1`.

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
- improve: three rules were strengthened after the first qwen gate run broke each of
  them — a missing `maturity` field is dropped rather than read off the note's own
  frontmatter, a structure edit moves a whole line and never a sentence carved out of
  one, and one note gets one `improve` log line per session however many moves were
  applied. Each was promoted on a two-arm run where the candidate lost no case.
- `labs/companion/` holds an **unscored Candidate edit**: a rule on what quotation marks
  promise (a note's exact words, never the model's own phrasing). It ships in no release
  until #23 runs the two arms and promotes it.

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
