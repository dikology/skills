---
name: improve
description: Structural review of one note in an Obsidian vault. Reads the note and the notes that link to it, then replies with a diagnosis (structure, content gaps, split/merge, maturity) ending in numbered proposed moves and questions. Writes nothing until the human approves moves by number, then applies only those, keeping the human's prose verbatim. Use for "/improve [[note]]", "improve this", or "improve <note>".
---

# Improve

Diagnose first, edit after. The diagnosis turn changes no file: no edit, no stub,
no log line. The human reads it and approves moves by number.

## Requires from the consuming vault

Outside dependencies, declared here rather than linked. All come from the
**Overlay**: a `## Improve` section in the vault's `CLAUDE.md` or `AGENTS.md`,
read as prose. Every field is optional, and a field may point at another section
("index, log, skip list: as in `## Companion`").

- **index** — the catalogue a promoted note joins. Absent: skip the index step,
  and drop the INDEX line from the diagnosis.
- **log** — a file that takes one line per note per session, and optionally its op
  vocabulary (default ops `improve`, `promote`, `split`). Absent: write nothing.
- **schema** — where the expected sections for each note type live, and the
  frontmatter property that names the type. Absent: infer the expected structure
  from the note and its siblings, and say so.
- **maturity** — the frontmatter property, its ladder (lowest first), and the
  level at which a note joins the index. Absent: no promotion moves, and no
  MATURITY section.
- **verification marker** — how an unsourced claim is flagged. Absent: an HTML
  comment, `<!-- NEEDS VERIFICATION: <reason> -->`.
- **skip list** — text that is never the human's voice. Absent: folded
  `> [!quote]- AI capture` callouts only.

Extra instructions after these fields are the vault's own; follow them, but never
need them.

## 1. Find the Overlay

Look for `## Improve` in the vault root's `CLAUDE.md` or `AGENTS.md`. Name each
missing field once, with its fallback, in the diagnosis header, then go on. With
no Overlay at all, say "No `## Improve` Overlay found", name every fallback once,
and go on. Never write an Overlay.

## 2. Pick one note

One note per run. `/improve [[note]]` names it; "improve this" means the note the
human is in. A folder, or several notes, gets a short list of candidates and the
question "which one first?", and nothing else.

## 3. Read the neighbourhood

Before writing a word of the diagnosis:

1. The note in full, and its frontmatter.
2. Its inbound links: every note linking to it by name or by any of its
   `aliases`. Skim the lines around each link to see how the note is used: a hub
   many notes lean on, a leaf, or an orphan nobody links to.
3. With a schema: the expected sections for this note's type.
   With none: the shape of two or three sibling notes of the same kind.
4. With an index: whether the note is listed, and where.

Skip-listed text is context, never the human's claim: don't count it as a gap,
don't flag it, don't propose rewording it.

## 4. Diagnose (writes nothing)

Reply in the language the human writes in. Quotes from the note stay verbatim in
their source language. Use this shape; drop a line or section whose Overlay field
is missing instead of filling it with a guess.

```
PAGE:       garden/compost.md
TYPE/MAT:   concept / growing
INBOUND:    5 links (3 from [[allotment diary]], 1 via alias "the heap", 1 from [[spring jobs]])
INDEX:      not listed
FALLBACKS:  no verification marker set, using <!-- NEEDS VERIFICATION -->

STRUCTURE
- Has: a long opening paragraph, a section on what goes in
- Missing: a one-sentence Definition at the top (schema: concept)
- Missing: Related and Sources sections

CONTENT GAPS
- "hot composting" is used three times and never defined
- Mentions bokashi but doesn't link it; no note exists for it yet
- Unsourced: "a heap turned weekly is ready in six weeks"

SPLIT/MERGE
- The paragraph on the wormery is a third of the note and could be [[wormery]].
  No other note talks about the wormery yet, so not yet.

MATURITY
- growing. A Definition, a Related section and a source for the six-weeks claim
  make it ready for solid. Five inbound links already lean on it.

PROPOSED MOVES (ranked)
1. Add a one-sentence Definition at the top. I draft it; your prose below stays as written.
2. Add Related (linking [[allotment diary]], [[spring jobs]]) and an empty Sources section.
3. Flag "a heap turned weekly is ready in six weeks" with the verification marker.
4. Create a [[bokashi]] stub at seed, linked both ways.
5. Promote to solid once 1–3 are done, and add it to the index.
6. NOT YET: split out [[wormery]]. Wait until another note uses it.

QUESTIONS
- Is the wormery part of composting for you, or its own project?
- Is "hot composting" your method, or one you read about?

Approve by number ("1, 2, 4"), "all", or "none" with another angle.
```

Moves are ranked: the cheapest change that most improves the note comes first.
Deferred moves stay in the list as `NOT YET: <move>. <reason>`, so the human sees
what was considered.

Then stop and wait. Do not edit, create a stub, or log in this turn.

### Improvement patterns

| Symptom | Typical move |
|---|---|
| No clear definition | A one-sentence Definition at the top |
| Rambling body | Section headings from the schema, or from sibling notes |
| Many inbound links, little content | Make it a hub: a Related list and outbound links |
| Much content, no inbound links | Likely an orphan: find two or three notes to link from |
| A concept mentioned but not linked | Wrap it in `[[…]]`; propose a stub if no note exists |
| A claim with no source | Flag it with the verification marker |
| Two concerns in one note | Propose a split, NOT YET until other notes use the second |
| One topic plus a long aside | Propose extracting the aside |

## 5. Apply what was approved

Only after the human names moves. A move they didn't name is declined; silence is
never approval. If their answers to the QUESTIONS change the moves, show the
revised list and wait again before writing.

## Rules

- **The diagnosis never writes.** Not a section, not a stub, not a log line.
- **Keep the human's prose verbatim.** Structure edits move and frame existing
  lines; they never reword them. Rewrite prose only when the human asks for it.
- **Skip-listed text is never the human's voice.** Never reword it or treat it as
  their claim.
- **At most three new stubs per run.** Each is a commitment.
- **Promotion is proposed, never applied without approval.**
