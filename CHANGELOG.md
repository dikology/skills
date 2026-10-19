# Changelog

All notable changes to this Library. Versions follow [semver](https://semver.org);
the Library stays on 0.x until companion has run about ten real sessions with no
workaround and its evals pass.

## [0.1.0-dev] — unreleased

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
