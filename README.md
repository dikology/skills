# skills

Agent skills for people who think in an Obsidian vault. MIT licensed, versioned,
and installable as a Claude Code plugin marketplace.

| Skill | What it does |
|---|---|
| [`companion`](skills/companion/SKILL.md) | A challenger-style thinking partner. It reads your notes before it speaks, takes a position, quotes your own past writing where it contradicts you, and ends every session with a next-move menu. |
| [`improve`](skills/improve/SKILL.md) | A structural review of one note. It reads the note and the notes that link to it, replies with a diagnosis ending in numbered proposed moves, changes no file until you approve moves by number, then applies only those, keeps your prose verbatim, and logs what it did. |

Status: **0.1.1 is released; 0.2.0 is in preparation** and not tagged yet, so pinning a
0.2.0 tag will not work until it ships. This stays 0.x until about ten real-vault
sessions need no workaround, so the Overlay contract may still change.
See [CHANGELOG](CHANGELOG.md).

[中文版 README](README.zh.md)

## Install

**Claude Code**

```
/plugin marketplace add dikology/skills
/plugin install dikology@dikology-skills
```

To pin a version, add the marketplace at a release tag instead, so the skills
don't change under you until you move the tag:

```
/plugin marketplace add https://github.com/dikology/skills.git#v0.1.1
/plugin install dikology@dikology-skills
```

Open your vault and run `/companion`, or say "challenge me on <topic>". To review
one note, run `/improve [[note]]`, or say "improve this" about the note you're in.

**Cursor, Codex or any agent that reads Agent Skills.** Each skill folder under `skills/`
is a plain skill. Copy `skills/companion/` and `skills/improve/` into your agent's
skills directory — for qwen that is `.qwen/skills/<name>/`, not `.claude/skills/`,
which qwen does not read.

## The pattern: generic skill + Overlay

A skill you use every day ends up full of your own specifics: your index page, your
log format, your folder names, examples from your own life. Publishing a "clean" fork
gives you two copies. You keep using the private one, and the public one rots.

This Library takes a different route ([ADR-0001](docs/adr/0001-overlay-not-fork.md)):

- **The skill is generic.** It assumes an Obsidian vault and nothing else.
- **Your vault holds an Overlay for each skill**: a short section named after it
  (`## Companion`, `## Improve`) in its `CLAUDE.md` or `AGENTS.md`, telling that skill
  where your things are. Install two skills and you have two Overlays; one may point
  at another in prose ("index, log, skip list: as in `## Companion`").
- **Every Overlay field has a fallback**, and the skill says out loud when it uses
  one. A vault with no Overlay still gets a working session.

The skill lists what it expects from your vault in one place, its
`Requires from the consuming vault` section. An Overlay looks like this:

```markdown
## Companion

- index: [[home]]
- log: `journal/thinking-log.md`
- filing target: `## Lines I said`
- skip list: the `clippings/` folder
- soft topics: `health/`, #grief
- lang: zh

Also: when I mention a book, check `reading/` first.

## Improve

- index, log, skip list: as in `## Companion`
- schema: `meta/note-types.md`, the type is the `type:` property
- maturity: `status` — seed, growing, solid, stable; joins the index at solid
```

Here `lang: zh` pins replies to 中文, which turns thinking sessions into language
practice. Leave it out and companion replies in whatever language you write in.
Quotes from your notes always stay in their original language.

Every field is optional. When one is missing, the skill names it once and says which
fallback it uses.

**companion** reads `## Companion`:

| Field | What it tells companion | Fallback when absent |
|---|---|---|
| `index` | The page orient starts from | Search the vault for the topic |
| `log` | A file that takes one line per session; an unpicked Close menu is logged as `menu unpicked` and named once next session | Write nothing |
| `filing target` | The heading under which `[a]` files your own line, verbatim and dated, on the note the session was about | Hand the line back in chat for you to place |
| `skip list` | Notes, folders or callouts that are never your voice, so never quoted | Only folded `> [!quote]- AI capture` callouts and the log, which are skipped in every vault |
| `soft topics` | Folders or tags where the challenger posture is off: no positions, no devil's advocate | Only saying "this is raw" mid-session softens it |
| `lang` | A reply-language pin | Reply in the language you write in |

**improve** reads `## Improve`:

| Field | What it tells improve | Fallback when absent |
|---|---|---|
| `index` | The catalogue a promoted note joins | Skip the index step, and drop the INDEX line |
| `log` | A file that takes one line per note per session, and optionally its op vocabulary (default ops `improve`, `promote`, `split`) | Write nothing |
| `schema` | Where the expected sections per note type live, and the frontmatter property naming the type | Infer the structure from the note and its siblings, and say so |
| `maturity` | The frontmatter property, its ladder, and the level at which a note joins the index | No MATURITY section and no promotion moves, not even a deferred one |
| `verification marker` | How an unsourced claim is flagged | An HTML comment, `<!-- NEEDS VERIFICATION: <reason> -->` |
| `skip list` | Text that is never your voice, so never reworded, flagged or linked inside | Folded `> [!quote]- AI capture` callouts only |

With no `## Companion` Overlay at all, companion's first session says so, asks for
every field in one message, shows the section it would write, and writes it only after
you approve. Decline and the session runs anyway on the fallbacks. A vault with no
notes gets a chat-only session: no quotes, no contradictions.

With no `## Improve` Overlay, improve names all six fallbacks once in the diagnosis
header and goes on: it still reads the note, still proposes numbered moves, still
writes nothing until you approve. It never writes an Overlay for you. Either way the
hard rules are in the skill, not the Overlay: your prose stays verbatim unless you ask
for a rewrite, the diagnosis turn changes no file, and an unapproved move is declined.

Anything after the fields is your own instruction. The skill follows it but never
depends on it, so the same skill works in a vault that has none.

Every skill in this Library follows the same rule, so you can borrow the pattern for
your own skills: keep the skill generic, declare what it needs from the vault with a
fallback for each item, and let each vault say the rest.

## Repo map

- `skills/` holds the stable skills, the ones the plugin ships. It is the plugin root:
  an install copies this folder and nothing else. Its `.claude-plugin/` holds the
  plugin manifest.
- `labs/companion/` and `labs/improve/` are the Candidates: the working copies, one per
  skill, scored against the stable copy before either may replace it.
- `labs/evals/` is the eval harness: synthetic Fixture vaults, scripted sessions,
  graders. It runs any skill by name (`run_evals.py improve`), taking that skill's
  cases from `labs/evals/cases/<skill>.json`.
- `.claude-plugin/` at the repo root holds the marketplace manifest.
- `CONTEXT.md` is the glossary: Overlay, Corpus, Consuming vault, Fixture vault, Stable/Candidate.
- `docs/adr/` holds the decisions and the reasons behind them.

## License

[MIT](LICENSE)
