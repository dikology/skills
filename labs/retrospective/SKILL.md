---
name: retrospective
description: Retro over agent sessions — reads transcripts across projects, writes evidence-cited insights, proposes concrete Memory, Rule, Skill edit, and Issue changes approved by number, and files explicit Retro notes for later review. Use for "/retrospective", "retro", "session review", "what did we learn", and "/retrospective note". Not for journal reflection over dailies.
---

# Retrospective

Two jobs:

- **Retrospective:** review the visible current conversation or sessions in a Retro
  window, report cross-session **Insights**, and propose exact **Retro candidates**.
  The human replies with numbers, `all`, or `none`; execute that decision without
  asking about individual items.
- **Retro note:** file one intentional line in the shared Retro inbox. No hook or
  background capture feeds this workflow.

## Shared entrypoint

Resolve `<entrypoint>` to `scripts/retrospective.py` inside this skill folder. Run
every capability, session, note, destination, and state operation through
`python3 <entrypoint>`; adapter implementation details stay behind that boundary.

When the human explicitly selects an adapter, pass `--adapter <name>` to every
operation. Otherwise omit it and let the entrypoint select the runtime. Explicit
selection overrides `RETROSPECTIVE_ADAPTER`. An unknown runtime supports only the
visible current conversation and must not scan another agent's directories.

Start with:

```bash
python3 <entrypoint> capabilities [--adapter <name>]
```

The JSON response is the only machine-readable source of supported operations,
signals, and destinations. Omit unsupported operations, signals, and destinations
rather than substituting Claude-shaped behavior. `disclosures` names each known
limitation of that runtime; say which ones shaped the review in the final summary.

## Modes and modifiers

| Invocation | Mode |
|---|---|
| `/retrospective note <text>` | Note only; file it, confirm, stop |
| `/retrospective` with 10+ human prompts | Current conversation plus its own Retro notes |
| `/retrospective` in a fresh session | Multi-session, last 14 days |
| `/retrospective week`, `today`, `yesterday`, `Nd`, `YYYY-MM-DD` | Multi-session over that Retro window |

`in <project>` filters by a case-insensitive substring of the originating project
path. `lang zh` localizes Insights into 中文; each Retro candidate remains in its
destination file's language. Other explicit language modifiers follow the same rule.
System-temp projects are skipped unless the human explicitly requests their inclusion.

## Retro notes

Use only the visible current conversation and text the human explicitly asks to file.

### The human supplies the note text

Keep the text verbatim and add one separate context line, at most 240 characters,
explaining why it matters without restating it. The filing request approves those
exact lines:

```bash
python3 <entrypoint> note [--adapter <name>] \
  --text '<human text>' --context '<one short line>' --approve
```

Confirm only after the response reports `saved`. Include the session ID when present.

### The human asks for a note without supplying text

Draft one note line and context line, run the same command without `--approve`, show
the proposal, and ask whether to file it. The response must be `approval_required`;
no note exists yet. Only approval of those exact lines licenses rerunning with
`--approve`. Any other decision leaves the inbox unchanged.

## Gather

### Current conversation

Analyze the visible conversation itself; do not reread a transcript to reconstruct
it. Optionally run `current-session`, then retrieve only notes with that complete
session ID:

```bash
python3 <entrypoint> current-session [--adapter <name>]
python3 <entrypoint> notes [--adapter <name>] --session-id '<complete ID>'
```

If identity is unavailable, do not attribute other sessions' notes to this
conversation. Claude identity uses the newest transcript modification time. Parallel
Claude sessions can therefore identify another active session; this fallback is not a
reliable per-process identity mechanism. Qwen identity comes from the session environment
its CLI exports, so parallel Qwen sessions are told apart; with no session environment,
`current-session` reports `unavailable` and a note is still filed without an identity.

### Multi-session

Run the shared digest with the selected Retro window and optional filter:

```bash
python3 <entrypoint> digest [--adapter <name>] --window 14d \
  [--project '<path substring>'] [--lang zh]
```

Add `--include-temp` only when requested. Drill into at most five interesting full
sessions, prioritizing corrections, errors, interruptions, friction, and Retro notes:

```bash
python3 <entrypoint> digest [--adapter <name>] \
  --session '<id or unique prefix>' [--session '<another>' ...]
```

A full-session request ignores the window and minimum-prompt filter. The digest lists
normalized sessions, evidence, handled-state IDs, open Retro notes, and previously
declined retro_candidate keys. Malformed input warnings are data-availability limitations,
not a clean review.

Claude `/insights` facets and claude-reflect queue entries appear only when present.
Both stores are read-only. Never clear the reflect queue; if covered items remain,
mention `/claude-reflect:skip-reflect` in the final summary. Missing signal stores
produce no empty signal sections.

Qwen discovery reads its native transcript store — `projects/<slug>/chats/` under
`$QWEN_RUNTIME_DIR`, else `$QWEN_HOME`, else `~/.qwen` — preferring the project folder the
CLI points at and traversing that storage root when the pointer is absent. A slug is a
lossy rendering of a path: the originating project comes from the transcript's own working
directory records, never from the folder name, and a session whose project cannot be
recovered still supports Insights while its project-bound writes stay blocked. Transcripts
of delegated agents under `projects/<slug>/subagents/` are not sessions and add nothing to
a human-prompt count. Qwen attributes a Skill only where the run recorded one (a slash
command sent to the model, or a Skill tool call), so an empty skills line is not evidence
that none was used. No process registry, credential file, or generated memory index is
read; an empty store is a data-availability warning, not an empty history.

## Prepare the report

Read the current destination state by passing up to seven retro_candidate objects through
`prepare`. Each object needs a stable shared `key`, `type`, originating `project`, and
exact proposed `text`. Use `memory`, `rule`, `skill_edit`, or `issue` only when listed
in capabilities.

```bash
python3 <entrypoint> prepare [--adapter <name>] \
  --retro-candidate '<retro_candidate JSON>' [--retro-candidate '<retro_candidate JSON>' ...]
```

Every Retro candidate also carries full `session_ids` or `note_ids` supporting it and
human-facing `citations`. A Retro note can support a Retro candidate independently of its
session's reviewed state.

Retro candidate destination fields:

- **Memory:** kebab-case `name`, `title`, `description`, `memory_type`
  (`user`, `feedback`, `project`, or `reference`), exact body `text`, and for
  feedback/project memories the `why` and `how_to_apply` lines. Memory is a Claude
  destination: where capabilities omit it, propose the observation as a Rule or an Issue
  instead, and never write a generated memory index.
- **Rule:** exact insertion `text`; optional exact `anchor` after which to insert.
  Claude selects the originating project's `AGENTS.md` when it exists, otherwise
  `CLAUDE.md`. Qwen writes a Qwen-only rule to the originating project's `QWEN.md`, and
  `scope: "cross_tool"` selects `AGENTS.md` for a rule meant for every agent. A personal or
  global instruction file needs `scope: "global"` and `explicit_user_direction: true` — the
  human's own request, never the run's inference.
- **Skill edit:** loaded Skill `name`, exact `old` source text, and exact replacement
  `text`. The adapter resolves symlinks to the canonical source. Plugin, built-in,
  extension, retrospective-self, and missing sources are never edited in place.
- **Issue:** exact `title` and body `text`, including the problem, session evidence,
  and proposed fix. Execution requires a GitHub `origin` in the originating project
  and adds `needs-triage` when that label exists.

Keep the prepared JSON objects unchanged for execution. Their target and expected
contents are the conflict-detection snapshot. Drop duplicates from the report. Never
write optional-signal stores, plugin caches, or this retrospective skill.

Sessions marked `reviewed` inform Insights but cannot independently generate Retro
retro_candidates. Never propose a key under **Declined before**, regardless of adapter.
Project-bound retro_candidates always use the evidence's originating project, not the
project where the review happens to run. Unknown project identity may support an
Insight but blocks a project-bound write.

For a multi-session Retrospective, build 4–6 Insight objects with `text`, at least
two full `session_ids`, and at least two corresponding human-facing `citations`. Pass
them with every prepared Retro candidate. Pass every full `session-id` printed by the
digest and every shown Retro note ID so the report can validate its evidence scope:

```bash
python3 <entrypoint> report [--adapter <name>] \
  --insight '<Insight JSON>' [--insight '<Insight JSON>' ...] \
  --digest-session-id '<complete session ID>' [--digest-session-id ...] \
  [--digest-note-id '<shown note ID>' ...] \
  [--retro-candidate '<prepared Retro candidate JSON>' ...]
```

Every Insight must use at least two distinct digest sessions. Every session or note
supporting a Retro candidate must have a corresponding citation containing its full
ID or unique short ID.

The response contains the rendered `report`, included `retro_candidates`, and
`suppressed` keys with reasons. The shared operation removes declined, reviewed-only,
duplicate, and unsafe entries before numbering. Print the report field verbatim and
retain only the included objects, in their returned order, for execution.

## Report

**Insights:** 4–6 bullets for a multi-session Retrospective. Each describes a pattern
across sessions and cites evidence as `project · short-id` or the Retro note ID.
Cover failures and detours, at most one practice worth keeping, where time went, and
one concrete pointer forward. Do not quote the agent's words as the human's view.

**Retro candidates:** at most seven, numbered and ranked by signal:

1. Retro notes and human corrections
2. Skills that failed or needed a workaround
3. Repeated patterns
4. Error patterns
5. Workflow patterns, such as the same 3+ Skill chain

Show each retro_candidate's destination, originating project, exact proposed text, and
citations. An upstream Skill retro_candidate is labeled **Skill edit (upstream)**. A session
with no Skill evidence gets no Skill edit retro_candidate. The prepared JSON need not be
printed, but the exact human-facing text must match it.

Close with exactly:

`Reply with numbers (e.g. 1 3), all, or none.`

## Execute and finish bookkeeping

The human's reply is the only approval. Do not confirm each item again. Execution uses
the objects `report` returned, field for field: their `target` and `expected` contents are
the conflict snapshot, and a candidate re-typed without them is refused as a conflict and
writes nothing. When the approval arrives in a later turn than the report — so those objects
are no longer in hand — save the `report` response to a file when the report is printed (for
example `"$TMPDIR/retrospective-report.json"`) and pass its `retro_candidates` back
unchanged. Pass every included
retro_candidate in report order, the original numeric/`all`/`none` response, every
session ID shown in the digest, and every Retro note ID shown:

```bash
python3 <entrypoint> execute [--adapter <name>] --approval '1 3' \
  --retro-candidate '<prepared retro_candidate 1 JSON>' \
  --retro-candidate '<prepared retro_candidate 2 JSON>' \
  [--session-id '<complete session ID>' ...] \
  [--note-id '<handled note ID>' ...]
```

`all` selects every non-Issue retro_candidate; `none` selects none. GitHub Issues require an
explicit numeric approval, so `all` is rejected before any action when an Issue is
included. One numeric response may select multiple items. Execution re-reads every
target, skips duplicates and post-report
conflicts with warnings, and never overwrites a conflicting edit. An unapproved Issue
causes no GitHub command.

The same operation marks all digest sessions reviewed for this adapter, records every
unselected retro_candidate key as declined, and clears every Retro note shown whether or
not its retro_candidate was selected. `none` performs only this bookkeeping.

Respond with one line per saved, skipped, duplicate, conflict, or upstream action and
a final ledger line giving reviewed, declined, and cleared counts. Add the read-only
claude-reflect reminder when applicable. Do not add another proposal or confirmation.

## State

The shared Retro inbox is `~/.retrospective/inbox.jsonl`. Set
`RETROSPECTIVE_STATE_DIR` to use a different parent directory. Reviewed and declined
state use `reviewed.txt` and `declined.txt` there. Reviewed identities are
`<adapter>:<complete opaque session ID>`; legacy bare UUIDs remain Claude IDs.
Declined keys and notes are shared across adapters.

Manual state operations remain available:

```bash
python3 <entrypoint> reviewed [--adapter <name>] \
  --session-id '<opaque ID>' [--session-id ...] [--check]
python3 <entrypoint> declined [--adapter <name>] \
  --retro-candidate '<retro_candidate key>' [--retro-candidate ...] [--check]
python3 <entrypoint> clear [--adapter <name>] \
  --note-id '<note ID>' [--note-id ...]
```

State mutations preserve unknown hand-edited lines, serialize through a lock, and
replace files atomically.
