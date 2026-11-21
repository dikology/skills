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

**Two-shape scan**:
What companion does to its own reply before sending it: read the sentences, find the ones holding both a Mark and a link, and keep only the two shapes allowed to hold both — the quote line, where the Span is the note's characters, and the Close menu's `[a]` line, where the Span is the human's. Any other sentence that holds both puts its Span on a quote line or says the note's meaning unmarked. Named for those two shapes, not for a tool. The Span audit's **line** is the outer bound — a wrapped paragraph is one line as its reader sees it — and inside it the reach stops at a sentence end (`。！？`, or `.!?` before a word), at another Mark, or at a loose bracket; a 中文 sentence runs on past `，；、` and `——`, which is where the reach is wider than it looks.
_Avoid_: lint, self-check, pre-send check

**Script test**:
The cheap half of the Two-shape scan, for a reply that is not in the Corpus's language: a Span written in the reply's own language is not a copy, because in that reply the only two voices are the note's characters and the human's. Naming a line (`那句`, `说的是`) hands nothing to the note — what follows is the reply's reading, and a reading wears no Mark. Silent where the reply is in the notes' language: there the script says nothing about who spoke, and what is left is the promise a Mark carries — nobody spoke the line companion composed for the human's unspoken meaning, so it wears no Mark.
_Avoid_: translation check, language guard

**Wrong door**:
A note's own characters put in `code` instead of in a Mark. Not a Span — `code` makes no promise that someone spoke — and so invisible to every grader: the copy is true, the owner is named nowhere, and the quote line it owes is never written. The third number the Span audit reports, beside broken and unowned.
_Avoid_: code span, misquoted, invisible copy

**Pointer form**:
The 中文 words companion uses to name one of a note's lines before saying what that line holds — `那句`, `说的是`, `记的是`. Pointing is not quoting: the form itself credits no voice, so what follows it is the reply's own reading unless something wraps it. Only a reply whose language is not the notes' has this need; an English reply names the line with its link instead.
_Avoid_: citation, reference, anaphora

**Pointer door**:
Which shape the content of a Pointer form takes. **Bare**: the reply's own words with nothing around them, which is a rendering that promises nothing. **Marked**: inside a Mark, which promises that someone spoke those words. **Weighed**: in `code`, which weighs a phrase and credits no note. Or no door at all, when the form points at a note's name, or the sentence stops there. A Mark and a bare run can hold the same 中文 characters and only the first claims a note said them, which is where the rendering defect lives: the Span audit counts the doors beside its three defect numbers, because the bare one makes no promise for those three to test.
_Avoid_: quote style, formatting, bracket

**Framing**:
The test a note applies to a thing — the question it answers with `worth it`, `a failure`, `enough`. companion carries a Framing from one note to another by naming the Framing in `code`, not by naming the note that taught it: a Framing is a sentence and a note is a file, and only the file can belong to a session the human already left unpicked.
_Avoid_: pattern, lens, mental model

**Case**:
One scripted conversation with a Fixture vault, beside the checks its replies must satisfy. The unit a skill is measured on; a skill's whole set of them is what a Gate spends.
_Avoid_: test, scenario, fixture

**Draw**:
One execution of one Case by one arm. Two draws of the same bytes can disagree, so a verdict from one draw says what came out, not what the copy is.
_Avoid_: run, retry, sample

**Flip**:
A Case passing on one draw of a copy and failing on another. A property of a probabilistic subject, not a defect found and re-found.
_Avoid_: flake, intermittence, noise

**Regression**:
The Candidate failing a Case that Stable passed — the only loss that answers "did I make anything worse?".
_Avoid_: flip, failure

**Shared flip**:
A Case both arms fail in the same Gate. Not a regression: the subject moved, and the change is blameless.
_Avoid_: regression, common defect

**Gate**:
The whole set of Draws spent to decide a release rather than to learn something. It is worth what its Draws are worth, so a Gate of one Draw per Case is a coin and a Gate of a rate is a measurement.
_Avoid_: checkpoint, suite, green build

**Shape-tight check**:
A check that passes only one way of building a sentence, so a reply that answers the Case well in another shape fails it. It may grade only a shape some copy of the skill teaches in prose; where it grades an untaught one it tests the harness's taste, not the skill.
_Avoid_: strict grader, hard test

**Broken rate**:
A Span audit's broken Spans beside the claim-bearing Marks they were drawn from, both printed. The number that says how well a copy keeps the quoting promise; a count with no denominator is a Draw, not a rate.
_Avoid_: zero broken, clean run

**Ticket**:
A numbered record in the Library's tracker that names one defect and carries the evidence about it. A Ticket is not a release criterion (ADR-0002).
_Avoid_: blocker, gate, milestone

**Closing criterion**:
The measurement that resolves a Ticket, stated about the mechanism the Ticket names and never about a release. A Ticket stays open while its mechanism is unfixed and closes when the fix is measured, whatever a tag is waiting for.
_Avoid_: gate, blocker, acceptance run
