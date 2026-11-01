# 门禁与验证

单一入口：`python3 scripts/check.py --all`，等价的短命令是 `make check`。`--list` 列 id 与一行说明，`--only <id>` 只跑一个 gate。

## 分层

| 层 | 何时跑 | 覆盖什么 | 入口 |
|---|---|---|---|
| 结构 | 每次提交 | 8 个 gate：frontmatter、sections、refs、forbidden_words、terms、budget、checklist、link_targets | `make check` |
| 自测 | 改过门禁、发布前 | 8 条破坏用例，确认对应 gate 会失败 | `make test-gates` |
| 用例 | 仅在用户明确要求时 | `evals/` 的 `input`、`expect`、`review` 逐条人工核对 | 手动执行，不进自动流程 |
| 人工 | 每次发布前 | 文档类型、结论可反驳性、删减是否真的发生、触发判断 | 评审清单，见 [authoring.md](authoring.md) |

结构层必须快：`check.py --all` 在 1 秒内跑完，所以能挂在每次提交。人工层每次针对一份真实文档，只在发布前做。两层不能互相替代：结构层证明形态成立，人工层证明内容可用。

用例层是手动层：`evals/` 不由 AI 自动运行，也不挂进 `check`、`test-gates`、pre-commit 或 CI。只有用户明确要求跑用例时才执行，结果记在本机。

## 八个 gate

所有 gate 独立执行，收集全部失败后统一输出，不 fail-fast。失败格式：

```
FAIL <id>
  <文件:行号> <原因>
    修复: <可复制的命令或动作>
```

通过的 gate 打印 `PASS <id>`，最后一行是 `通过 <n>/<m> 个 gate`。

| id | 检查什么 | 失败修复 |
|---|---|---|
| `frontmatter` | `SKILL.md` 的 frontmatter 可解析；`name` 等于 `doc-writing`；`description` 非空；`metadata` 是映射；`metadata.version` 存在且等于 `VERSION`；`metadata.category` 非空；`metadata.tags` 是非空列表 | `python3 scripts/check.py --only frontmatter`，按 FAIL 行改字段；版本不一致时同步 `VERSION` 与 `metadata.version` |
| `sections` | 二级标题恰好 10 个，按序含固定文字：交付物、入口：目的未判、五种文档，五道门禁、结构闸：结论前置、删减闸：写完必须删、AI 味六项、实例化、输出契约、硬性禁止、按需加载 | `python3 scripts/check.py --only sections`，按缺失、多余、乱序三类分别补齐 |
| `refs` | `references/` 下恰好 7 个 `.md`；每个相对路径在 `SKILL.md` 中出现恰好 1 次 | `python3 scripts/check.py --only refs`，补齐或删除参考文件，并让加载表恰好链接一次 |
| `forbidden_words` | `SKILL.md` 与 `references/` 不含 6 个模糊词与「随着…的发展」句式；引号内的反例引用与代码块不扫描 | `python3 scripts/check.py --only forbidden_words`，删词或改成可判定表述 |
| `terms` | `scripts/terms.json` 可解析；`terms` 是非空字符串列表，`forbidden` 是字符串列表；每个 term 在 `SKILL.md` 中出现；`forbidden` 词不出现在 `SKILL.md` 与 `references/` | `python3 scripts/check.py --only terms`；缺术语就在 `SKILL.md` 使用它，或从 `terms.json` 移除；禁用词改用规范术语 |
| `budget` | `scripts/budget.json` 的 `skill_lines`、`skill_chars`、`reference_lines` 是正整数；`SKILL.md` 行数与字符数、每个 reference 的行数不超限 | `python3 scripts/check.py --only budget`；先搬迁到 `references/`，再压缩 |
| `checklist` | `## 输出契约` 一节含 7 个字段名：类型、一句话结论、读者与决定、删减、证据强度、未验证、私有条件缺口 | `python3 scripts/check.py --only checklist`，补字段名 |
| `link_targets` | `SKILL.md` 里出现的每个 `references/*.md` 目标都真实存在；至少要有一个 | `python3 scripts/check.py --only link_targets`，创建目标或改链接 |

### 守卫

`refs` 兼作守卫：`references/` 下少于 7 个 `.md` 直接失败。参考文件被误删、glob 写错、或从错误的根目录运行时，其余 gate 可能全绿，因为它们检查的是空集合。`refs` 的计数把这种情况变成硬失败。

### 测试门禁的破坏法

门禁保护的是一个提示词文件，静默通过的 gate 比没有 gate 更危险。`scripts/test_gates.py` 把仓库复制到 `/tmp`，写入最小 fixtures，先确认基线通过，再逐条破坏规则，断言对应 gate 退出码为 1。

| 破坏 | 期望失败 |
|---|---|
| 把 `name` 改成 `other-skill` | `frontmatter` |
| 插入一个额外的二级标题 | `sections` |
| 在 `references/` 加一个 `extra.md` | `refs` |
| 在 `SKILL.md` 末尾追加一个模糊词 | `forbidden_words` |
| 在 `SKILL.md` 末尾追加一个 `terms.json` 里的禁用词 | `terms` |
| 把 `budget.json` 的 `skill_lines` 改成 5 | `budget` |
| 把输出契约里的「未验证：」改成「未核验：」 | `checklist` |
| 把 `references/kinds.md` 改成 `references/not-exist.md` | `link_targets` |

它只证明 gate 会失败，不证明 gate 的判据正确。判据的正确性由 [authoring.md](authoring.md) 的影响矩阵与人工评审保证。自测不进 pre-commit：每次复制仓库并跑 16 次 gate，耗时高于单次 check。

## 预算

| 对象 | 行上限 | 字符上限 |
|---|---|---|
| `SKILL.md` | 180 | 9000 |
| `references/*.md` | 120 | 无 |

数值只在 `scripts/budget.json`，由 `budget` gate 读取。`docs/` 与 `AGENTS.md` 不在预算内，超长由人工评审处理。

规则：

- 超限即失败，没有预警档。
- 超限先搬迁到 `references/`，再压缩，最后才改 `budget.json`，并在 `CHANGELOG.md` 写明为什么前两步不够。
- `SKILL.md` 的行数与字符数同时受限：只拆行不删字过不了字符检查，只删字不拆行过不了行数检查。

## 结构门禁与人工评审的分工

| 项 | 为什么机器判不了 | 谁来做 |
|---|---|---|
| 文档类型判得对不对 | 类型挂在读者动作上，标题与正文都可能骗过规则 | 人工读一句话结论与读者决定 |
| 元信息是否漏进正文 | 规则能查字段，判不了正文里是否混入作者视角的说明 | 人工通读正文，查类型、读者、删减、证据标签 |
| 一句话结论是否可反驳 | 规则能定位首段，判不了那是不是一个判断 | 人工逐句读首段 |
| 删减是否真的发生 | 报告层能证明写了数字，不能证明删的是承重节以外的东西 | 人工对照删减记录与正文 |
| 证据强度标得对不对 | 观测、推断、叙事的边界需要读数据来源 | 人工抽读结论句 |
| ADR 是否完整、是否被 design.md 链接 | 没有 gate 检查 ADR 结构 | 人工按 [docs/decisions/](decisions/) 的格式核对 |
| 触发判断 | 真实用户措辞无穷，`router_cases.yaml` 只是样本 | 人工抽样真实调用记录 |

机器门禁通过只代表形态正确。把上面几项也写成 gate，会让门禁依赖主观打分，最终变成"看起来通过"。

## 失败时的定位顺序

| 顺序 | 动作 | 目的 |
|---|---|---|
| 1 | `python3 scripts/check.py --only <id>` | 把范围缩到一个 gate，拿到具体文件行号 |
| 2 | 读 FAIL 块里的「修复」提示 | 多数失败是路径、字段、编号这类机械问题 |
| 3 | `git diff` 对照 [authoring.md](authoring.md) 的影响矩阵 | 确认是否漏改了连锁文件 |
| 4 | `python3 scripts/check.py --all` 全量重跑 | 单 gate 通过不代表其它 gate 不受同一改动影响 |
| 5 | 人工读 [evals/cases.yaml](../evals/cases.yaml) 的 `review` 清单 | 区分是提示词退步还是用例过严 |
