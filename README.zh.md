# skills

给用 Obsidian 笔记库思考的人写的智能体技能（Agent Skills）。MIT 许可，有版本号，
可以作为 Claude Code 插件市场安装。

[English README](README.md)

| 技能 | 作用 |
|---|---|
| [`companion`](skills/companion/SKILL.md) | 一个会反驳你的思考伙伴。开口之前先读你的笔记，表明立场；你现在说的话和过去写的矛盾时，它会把你自己的原话引出来；每次对话都以一份"下一步"菜单收尾。 |
| [`improve`](skills/improve/SKILL.md) | 一篇笔记的结构审阅。它读完这篇笔记和所有链接到它的笔记，回给你一份以编号"待改项"收尾的诊断；在你按编号批准之前，它一个文件都不改。批准后只改你点名的那几条，你的原文一字不动，并把做过的事记进日志。 |

状态：**0.1.1 已发布；0.2.0 正在准备，还没打标签**，所以按 0.2.0 标签固定安装暂时还不
可用。在大约十次真实笔记库的会话都不再需要变通之前，版本号保持 0.x，
所以 Overlay 的约定还可能变。变更见 [CHANGELOG](CHANGELOG.md)。

## 安装

**Claude Code**

```
/plugin marketplace add dikology/skills
/plugin install dikology@dikology-skills
```

想固定版本，就按发布标签添加市场。在你改标签之前，技能不会自己变：

```
/plugin marketplace add https://github.com/dikology/skills.git#v0.1.1
/plugin install dikology@dikology-skills
```

打开你的笔记库，运行 `/companion`，或者直接说
"challenge me on <话题>"。想审阅一篇笔记，运行 `/improve [[笔记名]]`，或者
就在你正在看的那篇里说"improve this"。

**Cursor、Codex 或任何能读 Agent Skills 的智能体。** `skills/` 下的每个技能文件夹都是
一个普通的技能。把 `skills/companion/` 和 `skills/improve/` 复制到你的智能体的技能
目录即可——qwen 认的是 `.qwen/skills/<技能名>/`，它不读 `.claude/skills/`。

## 做法：通用技能 + Overlay

一个天天用的技能，慢慢会塞满你自己的细节：你的索引页、你的日志格式、你的文件夹名、
你自己生活里的例子。再发布一个"干净"的分叉，你就有了两份：你继续用私有的那份，
公开的那份慢慢烂掉。

这个库换了条路（[ADR-0001](docs/adr/0001-overlay-not-fork.md)，英文）：

- **技能是通用的。** 它只假设有一个 Obsidian 笔记库，别的什么都不假设。
- **每个技能在你的笔记库里各有一个 Overlay**：在 `CLAUDE.md` 或 `AGENTS.md` 里加一小节，
  用技能的名字命名（`## Companion`、`## Improve`），告诉那个技能你的东西在哪儿。
  装两个技能就是两节；其中一节可以用大白话指向另一节
  （"index, log, skip list: as in `## Companion`"）。
- **Overlay 的每个字段都有兜底做法**，技能用到兜底时会明说。没有 Overlay 的笔记库
  照样能正常对话。

技能需要笔记库提供什么，都写在一个地方：它的 `Requires from the consuming vault`
一节。Overlay 长这样：

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

字段名保持英文，技能按原样读取。

这里的 `lang: zh` 把回复固定成中文，思考的同时也在练中文。不写这一行，companion
就用你写的语言回复。从笔记里引用的原话永远保持原来的语言，不翻译。

每个字段都可以不写。缺了哪个，技能会说一次，并说明用什么兜底。

**companion** 读 `## Companion`：

| 字段 | 告诉 companion 什么 | 不写时的兜底 |
|---|---|---|
| `index` | orient 从哪一页开始 | 在笔记库里搜索这个话题 |
| `log` | 每次会话记一行的文件；没选的收尾菜单记为 `menu unpicked`，下次会话开头提一次 | 什么都不写 |
| `filing target` | `[a]` 把你自己的那句话原样、带日期，记在本次话题那篇笔记的哪个标题下 | 在对话里把那句话还给你，由你自己放 |
| `skip list` | 哪些笔记、文件夹或 callout 不是你的声音，永远不引用 | 只有折叠的 `> [!quote]- AI capture` callout 和日志，这两样在任何笔记库里都跳过 |
| `soft topics` | 在哪些文件夹或标签下关掉反驳姿态：不表明立场，不唱反调 | 只有在对话中说"这件事还很 raw，我还没缓过来"才会放软 |
| `lang` | 固定回复语言 | 用你写的语言回复 |

**improve** 读 `## Improve`：

| 字段 | 告诉 improve 什么 | 不写时的兜底 |
|---|---|---|
| `index` | 一篇晋升后的笔记进哪个目录 | 跳过目录这一步，诊断里也不出 INDEX 那行 |
| `log` | 每篇笔记每次会话记一行的文件，还可以有它的操作词表（默认 `improve`、`promote`、`split`） | 什么都不写 |
| `schema` | 每种笔记类型该有的小节写在哪儿，以及哪个 frontmatter 属性记着类型 | 从这篇笔记和它的同辈笔记推断结构，并说明是推的 |
| `maturity` | 那个 frontmatter 属性、它的阶梯，以及笔记到第几级进目录 | 不出 MATURITY 一节，也不提晋升，连暂缓的提议都没有 |
| `verification marker` | 没有出处的说法怎么标注 | 一条 HTML 注释 `<!-- NEEDS VERIFICATION: <reason> -->` |
| `skip list` | 哪些文字不是你的声音，于是不改写、不标注、不在里面加链接 | 只有折叠的 `> [!quote]- AI capture` callout |

完全没有 `## Companion` 时，第一次会话会说明这一点，用一条消息问齐所有字段，给你看它要写的
那一节，等你同意后才写入。拒绝也没关系，会话照样进行，全部走兜底。笔记库里没有笔记，
就是纯聊天模式：没有引用，也不指出矛盾。

完全没有 `## Improve` 时，improve 在诊断开头把六个兜底各说一次，然后照常往下做：
照样读完那篇笔记，照样给出编号的待改项，照样在你批准之前一个字都不写。它不会替你写
Overlay。两个技能都一样：有几条硬规则写在技能里，不靠 Overlay——你不明确要求改写，
你的原文就不动；诊断那一轮不改任何文件；没点名的待改项算拒绝。

字段后面写的都是你自己的指令。技能会照做，但从不依赖它们，所以同一个技能在没有这些
指令的笔记库里也能用。

这个库里的每个技能都守同一条规则，你也可以拿这个做法去写自己的技能：技能保持通用，
写明它需要笔记库提供什么、每一项的兜底是什么，其余的让每个笔记库自己说。

## 目录

- `skills/`：稳定版技能，插件发布的就是这些。它就是插件根目录：安装时只复制这个文件夹，
  其余都不带。插件清单在它里面的 `.claude-plugin/`。
- `labs/companion/` 和 `labs/improve/`：Candidate，每个技能一份工作副本。必须先和
  自己的稳定版对比打分，才能替换它。
- `labs/evals/`：评测工具：合成的 Fixture 笔记库、写好剧本的会话、评分器。按名字跑
  任何技能（`run_evals.py improve`），用例取自 `labs/evals/cases/<技能名>.json`。
- 仓库根目录的 `.claude-plugin/`：插件市场的清单文件。
- `GLOSSARY.md`：术语表（英文）：Overlay、Corpus、Consuming vault、Fixture vault、Stable/Candidate。
- `docs/adr/`：设计决定和背后的理由（英文）。

## 许可

[MIT](LICENSE)
