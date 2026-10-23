# skills

A public library of agent skills, shipped as a Claude Code plugin marketplace. Each
skill is generic; everything specific to one vault lives in that vault's Overlay.

## Language

**Library**:
This repository. Generic skills, their eval harness, and the records explaining them. It holds no one's real notes.
_Avoid_: vault, wiki

**Overlay**:
A `## Companion` section in a Consuming vault's `CLAUDE.md` or `AGENTS.md` that tells the generic skill where things are: index, log, filing target, skip list, soft topics, and an optional `lang` pin. Read by the agent as prose; there is no parser. Every field has a stated fallback. Free-form instructions may follow the fields.
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
