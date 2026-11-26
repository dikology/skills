---
name: retrospective
description: File an explicit Retro note for a later session review. Use for "/retrospective note", "/retro note", "file a Retro note", or "remember this for my retrospective". Multi-session analysis is not available yet.
---

# Retrospective

This Candidate currently files Retro notes. For any other retrospective request,
say that multi-session analysis is not implemented yet.

## Shared entrypoint

Resolve `<entrypoint>` to `scripts/retrospective.py` inside this skill folder. Run
every capability, current-session, and note operation through
`python3 <entrypoint>`; adapter implementation details stay behind that boundary.

When the human explicitly selects an adapter, pass `--adapter <name>` to every
operation. Otherwise omit it and let the entrypoint select the runtime. An
explicit `--adapter` also overrides the `RETROSPECTIVE_ADAPTER` environment
variable.

Start with:

```bash
python3 <entrypoint> capabilities [--adapter <name>]
```

The JSON response is the only source of supported operations, signals, and
destinations. Proceed with note mode only when it reports the note operation and
Retro inbox destination. Current-session identity is optional.

## File a Retro note

Use only the visible current conversation and text the human explicitly asks to
file. Notes are intentional user input; no hook or background capture feeds this
workflow.

### The human supplies the note text

1. Keep the human's note text verbatim. Write one separate context line, at most
   240 characters, saying why the note matters for a later review; do not restate
   the note.
2. The explicit filing request is approval for that supplied text. Run:

   ```bash
   python3 <entrypoint> note [--adapter <name>] \
     --text '<human text>' --context '<one short line>' --approve
   ```

3. Confirm only after the JSON response reports `saved`. Include the session ID
   when present, or say the note was saved without one.

### The human asks for a note without supplying text

1. Draft one note line from the visible conversation and one separate context
   line, at most 240 characters.
2. Run the note operation without `--approve`:

   ```bash
   python3 <entrypoint> note [--adapter <name>] \
     --text '<proposed line>' --context '<one short line>'
   ```

3. Show the proposed note and context and ask whether to file them. The response
   must report `approval_required`; no note exists at this point.
4. Only after the human approves those exact lines, rerun the same command with
   `--approve`. Confirm the `saved` response. Any other human decision leaves the
   inbox unchanged.

## Current-session lookup

To report identity independently of a note, run:

```bash
python3 <entrypoint> current-session [--adapter <name>]
```

An unavailable result is a valid outcome. It neither blocks a note nor licenses
searching another agent's directories.

## State

The shared Retro inbox is `~/.retrospective/inbox.jsonl`. Set
`RETROSPECTIVE_STATE_DIR` to use a different parent directory. Each saved JSON
record carries the note, context, adapter, optional session ID, project, and UTC
timestamp.
