# skills

Agent skills for people who think in an Obsidian vault. MIT licensed, versioned,
and installable as a Claude Code plugin marketplace.

| Skill | What it does |
|---|---|
| [`companion`](skills/companion/SKILL.md) | A challenger-style thinking partner. It reads your notes before it speaks, takes a position, quotes your own past writing where it contradicts you, and ends every session with a next-move menu. |

Status: **0.1.0**. This stays 0.x until about ten real-vault sessions need no
workaround, so the Overlay contract may still change. See [CHANGELOG](CHANGELOG.md).

[中文版 README](README.zh.md)

## Install

**Claude Code**

```
/plugin marketplace add dikology/skills
/plugin install dikology@dikology-skills
```

To pin a version, add the marketplace at a release tag instead, so the skill
doesn't change under you until you move the tag:

```
/plugin marketplace add https://github.com/dikology/skills.git#v0.1.0
/plugin install dikology@dikology-skills
```

Open your vault in Claude Code and run `/companion`, or say "challenge me on <topic>".

**Cursor, Codex or any agent that reads Agent Skills.** Each folder under `skills/`
is a plain skill. Copy `skills/companion/` into your agent's skills directory.

## The pattern: generic skill + Overlay

A skill you use every day ends up full of your own specifics: your index page, your
log format, your folder names, examples from your own life. Publishing a "clean" fork
gives you two copies. You keep using the private one, and the public one rots.

This Library takes a different route ([ADR-0001](docs/adr/0001-overlay-not-fork.md)):

- **The skill is generic.** It assumes an Obsidian vault and nothing else.
- **Your vault holds an Overlay**, a short section in its `CLAUDE.md` or `AGENTS.md`
  that tells the skill where your things are.
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
```

Here `lang: zh` pins replies to 中文, which turns thinking sessions into language
practice. Leave it out and companion replies in whatever language you write in.
Quotes from your notes always stay in their original language.

Every field is optional. When one is missing, companion names it once at the start
of the session with the fallback it uses:

| Field | What it tells companion | Fallback when absent |
|---|---|---|
| `index` | The page orient starts from | Search the vault for the topic |
| `log` | A file that takes one line per session; an unpicked Close menu is logged as `menu unpicked` and named once next session | Write nothing |
| `filing target` | The heading under which `[a]` files your own line, verbatim and dated, on the note the session was about | Hand the line back in chat for you to place |
| `skip list` | Notes, folders or callouts that are never your voice, so never quoted | Only folded `> [!quote]- AI capture` callouts and the log, which are skipped in every vault |
| `soft topics` | Folders or tags where the challenger posture is off: no positions, no devil's advocate | Only saying "this is raw" mid-session softens it |
| `lang` | A reply-language pin | Reply in the language you write in |

With no Overlay at all, the first session says so, asks for every field in one
message, shows the section it would write, and writes it only after you approve.
Decline and the session runs anyway on the fallbacks. A vault with no notes gets a
chat-only session: no quotes, no contradictions.

Anything after the fields is your own instruction. The skill follows it but never
depends on it, so the same skill works in a vault that has none.

Every skill in this Library follows the same rule, so you can borrow the pattern for
your own skills: keep the skill generic, declare what it needs from the vault with a
fallback for each item, and let each vault say the rest.

## Repo map

- `skills/` holds the stable skills, the ones the plugin ships.
- `labs/companion/` is the Candidate: the working copy of companion, scored against the
  stable one before it may replace it.
- `labs/evals/` is the eval harness: synthetic Fixture vaults, scripted sessions, graders.
- `.claude-plugin/` holds the marketplace and plugin manifests.
- `CONTEXT.md` is the glossary: Overlay, Corpus, Consuming vault, Fixture vault, Stable/Candidate.
- `docs/adr/` holds the decisions and the reasons behind them.

## License

[MIT](LICENSE)
