# Mutants

Deliberately broken copies of a skill. Each one shows that a case can fail: run it
with `--skill` and the case it targets should print FAIL.

| Mutant | Breaks | Should fail |
|---|---|---|
| `companion-paraphrase/` | Orient paraphrases the notes, with no quotes and no wikilinks | `orient-quotes-corpus` |

A mutant is a copy of the stable skill with one section changed. It is never
promoted and never shipped.
