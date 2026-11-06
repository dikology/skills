# skills

A public library of agent skills, shipped as a Claude Code plugin marketplace. Each
skill is generic; everything specific to one vault lives in that vault's Overlay.

## Language

**Library**:
This repository. Generic skills, their eval harness, and the records explaining them. It holds no one's real notes.
_Avoid_: vault, wiki

**Overlay**:
A section named after one skill (`## Companion`, `## Improve`) in a Consuming vault's `CLAUDE.md` or `AGENTS.md` that tells that skill where things are. Each skill lists its own fields in its `Requires from the consuming vault` section. Read by the agent as prose; there is no parser, so one section may point at another ("as in `## Companion`"). Every field has a stated fallback. Free-form instructions may follow the fields.
_Avoid_: config, settings, profile

**Corpus**:
The human's own notes in a vault, the material companion reads and quotes. Excludes everything on the skip list, including folded `AI capture` callouts. A vault with no corpus runs companion chat-only.
_Avoid_: knowledge base, data

**Consuming vault**:
An Obsidian vault where a Library skill is installed and run. The maintainer's own vault is one, with no special status.
_Avoid_: host, user vault

**Fixture vault**:
A small, hand-written, synthetic vault in the Library, built to provoke one behaviour in an eval case. Never real notes.
_Avoid_: test vault, sample data

**Stable / Candidate**:
Stable is the published copy of a skill under `skills/`; it changes only by promotion. Candidate is the working copy under `labs/`, scored against Stable on the same Fixture vaults before it may replace it. The two are the eval runner's arms.
_Avoid_: prod/dev, v1/v2

**Mark**:
The quotation marks themselves in a companion reply — `"`, `«»`, `“”`, `「」`, in any script. A mark is a promise that the words inside are someone's exact words; the **Span** is what sits inside them.
_Avoid_: quote mark, emphasis

**Span**:
One run of characters inside quotation marks in a reply — the unit the quoting promise is kept or broken on. A span either holds a note's or the human's exact words, or it claims that someone spoke when no one did.
_Avoid_: excerpt, quote fragment

**Span audit**:
Going through every Span in a run's replies and saying whose words each one holds, including the Spans no grader can see: a Span is a claim about a note only where its own line names one. The measurement behind any claim that a run quoted honestly, as distinct from a run that passed.
_Avoid_: lint, quote check

**Wrong door**:
A note's own characters put in `code` instead of in a Mark. Not a Span — `code` makes no promise that someone spoke — and so invisible to every grader: the copy is true, the owner is named nowhere, and the quote line it owes is never written. The third number the Span audit reports, beside broken and unowned.
_Avoid_: code span, misquoted, invisible copy

**Framing**:
The test a note applies to a thing — the question it answers with `worth it`, `a failure`, `enough`. companion carries a Framing from one note to another by naming the Framing in `code`, not by naming the note that taught it: a Framing is a sentence and a note is a file, and only the file can belong to a session the human already left unpicked.
_Avoid_: pattern, lens, mental model
