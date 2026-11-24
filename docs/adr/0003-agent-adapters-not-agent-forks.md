# ADR-0003 — Agent adapters, not agent forks

Status: accepted
Date: 2026-11-23

## Context

Retrospective began as a Claude-specific skill. Moving it into the Library requires
support for Claude, Qwen, and Kimi without maintaining three copies of the retrospective
workflow. The Library already uses Overlay for prose configuration of a Consuming vault;
that mechanism describes vault specifics, not agent runtimes, and retrospective does not
require a vault.

## Decision

**One agent-neutral retrospective skill, plus an Agent adapter for each supported runtime.**

- The Library is the only canonical source; the original skill is not independently developed.
- The shared core owns the retrospective workflow, inbox and ledger, windows, normalized
  sessions, digest rendering, and suppression of reviewed sessions and declined Retro candidates.
- The skill invokes one shared entrypoint; it never calls a runtime adapter directly from
  note mode or another core workflow.
- Claude, Qwen, and Kimi adapters own transcript discovery and parsing, current-session
  identification, runtime-specific destinations, and optional runtime signals.
- An explicit adapter choice takes precedence over runtime detection. An unknown runtime
  gets current-conversation analysis only; the skill does not infer a runtime from another
  agent's installed directories.
- Adapters declare their capabilities through a machine-readable contract. Unsupported
  destinations and signals are omitted or reported explicitly, never silently replaced with
  Claude-shaped behavior.
- A cross-session adapter supplies stable session identity, project identity, timestamps, and
  ordered human prompts. Other signals are optional; malformed sessions produce warnings rather
  than silently disappearing or blocking the whole Retrospective.
- One Retrospective run reads one adapter's sessions. It does not aggregate several agents, add
  telemetry, or introduce an external transcript service.
- Agent adapters are distinct from Overlays. Overlay retains the meaning in ADR-0001.

## Consequences

- Shared retrospective semantics have one implementation rather than three that can drift.
- Session identity is namespaced by adapter, while inbox and declined Retro candidates remain
  shared across agents. Existing Claude state remains readable without a mandatory rewrite;
  hand-edited state is preserved and updates are atomic and concurrency-safe.
- Adapter correctness needs fixture-backed integration evidence for each runtime. The Qwen
  behavioral Gate alone cannot establish Qwen or Kimi transcript and destination correctness.
- A runtime without a safe write destination can still produce a report, but cannot execute
  Retro candidates.

## Alternatives rejected

**One fork per agent.** Local adaptation is straightforward, but workflow, bookkeeping, and
suppression behavior would drift across three copies.

**Agent-specific Overlays.** Overlay is vault prose configuration with fallbacks, not a
transcript parser or runtime integration; broadening it would conflate two independent axes.

**A lowest-common-denominator skill.** Omitting every runtime-specific capability would make
all adapters artificially weaker instead of making optional capabilities explicit.
