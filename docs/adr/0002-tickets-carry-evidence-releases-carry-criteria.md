# ADR-0002 — Tickets carry evidence; releases carry criteria

Status: accepted
Date: 2026-11-20

## Context

Every open companion Ticket writes its closing criterion as a release run. #24 and #25 each
say "all 20 companion cases at 20/20 both arms"; #27 and #28 say the same both-arm run plus
their own measurement. #17 is that run. So no Ticket can close until a Gate passes, and a
Gate — 42 or 52 rows of real model sessions, ~9M to ~12M tokens — is one Draw per Case on a
probabilistic subject, where P(no Case fails on both arms) sits near 0.72 whatever ships.

Three consequences showed up in the record before the decision was made. #24 and #25 are
resolved on measurement and have been for weeks, yet stayed open because the run had not
landed. #26 was closed on 2026-11-20 while the bytes it scored still write 3 broken Spans,
which reads as a contradiction only because a closure was asked to mean "the release is
clear". And a shared flip — one Case failing in the same Gate on bytes that are identical
after promotion — could keep a defect record open that nobody disputes.

## Decision

**A Ticket's closing criterion is a measurement of the mechanism the Ticket names. A
release's criteria are the release's own, in one place.** A Ticket closes when its fix is
measured, and never because a Gate came up green; a Gate passes or fails on its own clause
and never closes a Ticket by passing. Where a defect is known and deliberately shipped, it
stays a Ticket with a line in the release note, not a blocker on the tag.

## Consequences

- The release criteria live in #17 alone. Editing a Ticket's box stops being a way to edit
  the bar.
- #24 and #25 close on the measurement already in their own bodies. #27 and #28 stay open as
  defect records with their gate clauses struck, and their defects appear as named lines in
  the release note.
- A Gate is judged as a rate with its denominator, not an all-or-nothing count, because one
  Draw per Case buys a coin flip at the price of a release. This is the shape #17's
  2026-11-06 amendment already gave the Span audit; it now applies to the verdicts too.
- A shipped defect no longer hides behind an open Ticket. It has to be written where a user
  will read it.

## Alternatives rejected

**Close everything and tag now.** Cheapest, and it throws away the only distinction the
Library has between "unmeasured" and "measured and accepted", which is the thing the eval
harness exists to keep.

**Keep Tickets gated on the run, and simply stop gating releases.** That only moves the
conflation: the release bar becomes five Ticket boxes with nobody reconciling them, which is
how "0 broken spans" and "20 cases" both ended up written down as current.

**One release branch per Ticket.** Real isolation, wrong cost: every Ticket would pay its own
both-arm run, so the spend multiplies by the number of open defects to buy what a shared run
already measures.
