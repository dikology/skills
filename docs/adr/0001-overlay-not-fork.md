# ADR-0001 — Overlay, not fork

Status: accepted
Date: 2026-10-18

## Context

Companion began as a skill in one vault. It worked there because it hard-coded that
vault: its index page, its log format, its note maturity levels, its hooks into
sibling skills, and examples quoted from the owner's own notes. To publish it, the
specifics have to come out. They are also what makes it useful in the vault it came
from, so they can't be dropped.

The failure to avoid is two copies. A public copy and a private copy drift, the
owner only runs the private one, and the public one rots without anyone noticing.

## Decision

**One generic skill, plus a per-skill Overlay.**

- The skill in this Library assumes an Obsidian vault and nothing else about it.
- An Overlay is a section named after one skill (`## Companion`, `## Improve`), not one
  section per vault: a vault that installs two skills has two Overlays, and one may
  point at another in prose ("index, log, skip list: as in `## Companion`").
- Each Consuming vault declares companion's specifics in a `## Companion` section of its
  `CLAUDE.md` or `AGENTS.md`: index, log, filing target, skip list, soft topics, and
  an optional `lang` pin. The agent reads it as prose.
- Every field has a fallback the skill names out loud when it applies, so a vault
  with no Overlay still gets a working session.
- Vault-specific behaviour beyond the fields goes in the Overlay as free-form
  instructions. The generic skill must never depend on them.
- The maintainer's vault installs the published plugin and keeps its specifics in
  its Overlay. Fixes land in the Library.

## Consequences

- The maintainer runs the public skill daily, so its defects surface where they can
  be fixed.
- The skill's assumptions about the vault are listed in one place, its
  `Requires from the consuming vault` section.
- Overlay reading is behaviour, not code: it can only be tested through a session
  against a Fixture vault, not unit-tested.
- A vault's free-form instructions can quietly contradict the skill. That conflict
  is resolved by the agent at run time, and is the vault's to fix.

## Alternatives rejected

**Public/private fork pair.** Simple on day one, and drift starts the same day. The
private fork gets the fixes because it is the one in use.

**Install-time templating.** Placeholders filled in when the skill is copied. That
needs an installer, breaks the plain-folder install for other agents, and freezes
the values at install time, so changing your log file means reinstalling.

**A config file with a schema.** Machine-checkable, but it adds a parser and a
format to a contract the agent already reads well as prose, and it has no place
for free-form instructions.
