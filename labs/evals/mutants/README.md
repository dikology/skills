# Mutants

Deliberately broken copies of a skill. Each one shows that a case can fail: run it
with `--skill` and the case it targets should print FAIL.

| Mutant | Breaks | Should fail |
|---|---|---|
| `companion-paraphrase/` | Orient paraphrases the notes, with no quotes and no wikilinks | `orient-quotes-corpus` |
| `companion-no-voice-guard/` | Quotes any note, `AI capture` callouts and skip-listed notes included | `callout-never-quoted`, `skip-list-never-quoted` |
| `companion-no-soft-mode/` | Ignores soft topics and the raw flag: the challenger posture never drops | `soft-topic-no-pushback`, `raw-flag-softens` |
| `companion-no-contradiction-guard/` | The contradiction step: paraphrases the conflict instead of quoting both positions, names the type for the human, and rewrites the older note instead of annotating it | `contradiction-typed`, `reversal-annotated` |

A mutant is a copy of the stable skill with one behaviour broken, and only the
lines that carry it changed. It is never
promoted and never shipped.
