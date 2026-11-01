# 版本产出流程

本文件回答一个问题：下一个版本怎么产出。运行时入口是 [SKILL.md](../SKILL.md)，它才是唯一事实源；设计理由在 [design.md](design.md)，门禁细节在 [verification.md](verification.md)，术语在 [glossary.md](glossary.md)。

改任何行为前，先在本文件里找到对应的变更类型，再动手。

## 版本语义

| 版本位 | 触发条件 | 例子 |
|---|---|---|
| patch | 只改措辞、示例、错别字；类型集合、门禁表、报告层字段都不变 | 换一条 AI 味的失败签名措辞 |
| minor | 新增门禁条目、术语或参考文件；类型集合与报告层字段不变 | 在删减闸加一条密度判据 |
| major | 类型集合、三闸顺序、报告层字段、触发方式任一变化 | 五类文档合并为三类 |

判定顺序：报告层字段或触发方式变了就是 major；体检表没变、但类型集合或门禁条目有增删就是 minor；两者都没变才是 patch。版本号写两处：`SKILL.md` 的 `metadata.version` 与 `CHANGELOG.md` 顶部条目，由 `frontmatter` gate 比对。

**版本授权**：major 位只在用户明确要求升大版本时使用；日常维护只升 patch 或 minor。按上表属于 major 而用户未授权时，先做向后兼容或停下来确认，不得用 minor 伪装。

## 六步流程

以"新增一条渲染后页数上限"为例。每一步写明改哪个文件、跑哪条命令。

| 步 | 动作 | 文件 | 命令 |
|---|---|---|---|
| 1 | 写失败样例：一段真实会写坏的长文，加上期望的报告层检查记录 | 草稿，放 `/tmp` | 无 |
| 2 | 先把样例写成用例：填 `input`、`expect`、`review`、`why` | [evals/cases.yaml](../evals/cases.yaml) | `python3 -c 'import yaml;yaml.safe_load(open("evals/cases.yaml"))'` |
| 3 | 改承重件：类型表、三闸顺序、报告层字段三选一 | [SKILL.md](../SKILL.md) | `python3 scripts/check.py --all` |
| 4 | 细节搬迁：判据写进参考文件，新术语先进表 | `references/*.md`、[docs/glossary.md](glossary.md)、[scripts/terms.json](../scripts/terms.json) | `python3 scripts/check.py --all` |
| 5 | 跑结构门禁，再逐条人工核对用例，结果写进变更记录 | [CHANGELOG.md](../CHANGELOG.md) | `python3 scripts/check.py --all`，然后人工逐条读用例 |
| 6 | 升版本，按变更影响矩阵回填 | [SKILL.md](../SKILL.md) 的 `metadata.version`、[CHANGELOG.md](../CHANGELOG.md) | `python3 scripts/check.py --only frontmatter` |

### 步 1 到 2：用例先写后改

先写用例，再改提示词。用例只测可观察量：文档类型、一句话结论的原句、被删除的节数、体检表行数、被否决方案是否出现、禁用替代词是否出现。不写"应该更有洞察力"这类判断。用例一写就通过，说明判据没抓住行为：换一个可观察量，或把输入改得更接近真实误用。

用例不自动运行。`evals/` 只在用户明确要求时手动执行，`check`、`test-gates`、pre-commit 与 CI 都不读它；结果记在本机，不回写仓库。

### 步 3：只动承重件

| 承重件 | 位置 | 改它的后果 |
|---|---|---|
| 类型判定与门禁表 | `SKILL.md` §2 | 判定标准变化，必须同步参考文件与用例 |
| 结构闸骨架表 | `SKILL.md` §3 | 检查点变化，必须同步用例 |
| 删减闸与 AI 味六项 | `SKILL.md` §4、§5 | 删除判据变化，必须同步 ADR 0003、0004 |
| 报告层检查记录 | `SKILL.md` §7 | 下游解析变化，通常升 major，必须同步 ADR 0005 与全部用例 |
| 实例化条件表 | `SKILL.md` §6 | 结构翻转条件变化，必须同步用例 |

解释性文字不是承重件。理由进 [design.md](design.md) 或 [docs/decisions/](decisions/)，示例进 `references/`。

### 步 4：入口只留承重件

`SKILL.md` 每个二级标题下只保留能被执行或被检查的内容。判据细节、反例、领域素材放 `references/`，按 `SKILL.md` §9 的加载表引用。每个 `references/*.md` 必须在 `SKILL.md` 中恰好链接一次，由 `refs` gate 检查。

新增术语的顺序固定：先写 [docs/glossary.md](glossary.md) 的定义与「不要写成」列，再加 [scripts/terms.json](../scripts/terms.json) 的 `terms` 与 `forbidden`，最后才在 `SKILL.md` 或 `references/` 使用。反序会让 `terms` gate 失败。

### 步 5：结构结果与人工结果都要记录

`python3 scripts/check.py --all` 记录通过的 gate 数。人工核对的用例记录三条：跑了几条、哪条 `review` 项没满足、与上一版差在哪。只写"已通过"不算记录。

### 步 6：版本与变更记录

`CHANGELOG.md` 在顶部加 `## [<version>] - <日期>`，分 Added / Changed / Removed / Migration 四节。破坏性变更必须写 Migration，读者只看这一节就知道旧版文档要改什么。

## 变更影响矩阵

| 改了什么 | 必须同时更新 | 由什么检查 |
|---|---|---|
| `SKILL.md` 的某道门禁 | `references/` 对应文件 + [evals/cases.yaml](../evals/cases.yaml) 至少 1 条用例 | `budget` + 人工 |
| 任一术语（新增、改名、退役） | [docs/glossary.md](glossary.md) + [scripts/terms.json](../scripts/terms.json) | `terms` |
| 报告层字段 | [0005 决策](decisions/0005-observable-checklist-output.md) + 用例的 `review` 清单 | `checklist` + 人工 |
| `description` 或触发条件 | [evals/router_cases.yaml](../evals/router_cases.yaml) | 人工 |
| 类型集合 | 五道门禁 + [0001 决策](decisions/0001-single-type-per-document.md) + 用例 | `sections`（标题变化时）+ 人工 |
| 删减闸判据 | [0003 决策](decisions/0003-deletion-as-primary-action.md) + `references/` 对应文件 | `budget` + 人工 |
| AI 味六项 | [0004 决策](decisions/0004-six-slop-dimensions.md) + 用例 | `budget` + 人工 |
| 增删参考文件 | `SKILL.md` §9 加载表，保证恰好链接一次 | `refs`、`link_targets` |
| 新增决策 | [docs/decisions/](decisions/) 的新 ADR + [design.md](design.md) 的索引表 | 无 gate，人工核对 |
| 调整预算 | `scripts/budget.json`，且先搬迁内容 | `budget` |

矩阵里的"至少 1 条用例"是下限。改门禁却没有能观察该门禁的用例，这条规则就不可测；不可测的规则会在下一次改动时静默失效。语义变化没有对应的 gate，靠人工评审兜底，靠用例留下可复查的记录。

### 矩阵的三种连锁

- 改门禁：先加或改用例，再改 `SKILL.md` 的门禁表，最后同步参考文件。顺序反了，参考文件与入口会各说一套。
- 改术语：旧词残留在 `references/` 或 `terms.json`。`terms` gate 查每个术语是否在 `SKILL.md` 出现，以及 `forbidden` 词是否混进 `SKILL.md` 与 `references/`。
- 改报告层：下游读的是行名与顺序。用例的 `review` 必须覆盖新行，否则测的是旧契约。
- 改报告层时同时确认文档层没有被塞进元信息：类型、读者、删减记录、证据标签都不该出现在正文。

## 写作规则

| 规则 | 判据 |
|---|---|
| 一条规则一个动作 | 读者能直接执行；"要严谨"不行，"先跑 P0 再贴标签"可以 |
| 能用表格不用段落 | 判据、映射、代价、失败签名一律表格 |
| 禁止模糊词 | 不用限定词替代判据；禁用清单见 [glossary.md](glossary.md) 的「不要写成」列 |
| 理由不进 `SKILL.md` | 理由写 [design.md](design.md) 或 ADR，入口只写动作 |
| 同一事实只写一处 | 其它位置只链接，不复述 |
| 每条新规则可观察 | 至少被一个 gate 或一条用例命中 |
| 术语逐字使用 | 未判、探针、门禁、目的闸、结构闸、删减闸、一句话结论、删节测试、混装、体检表、私有条件、承重件 |
| 不写计划句 | 只写当前事实，不写"我们将""计划中" |
| 例子最多两个 | 第三个例子说明该进 `references/` |
| 结尾不写总结段 | 最后一节就是最后一条规则 |

## 评审清单

逐条勾选，全部为"是"才提交。

- [ ] 1. 新行为有对应用例，且已人工核对；用例字段没有空项。
- [ ] 2. `python3 scripts/check.py --all` 全绿，通过的 gate 数没有减少。
- [ ] 3. 用例的 `review` 清单逐条勾选，失败项为 0。
- [ ] 4. `SKILL.md` 只增删了承重件，行数与字符数在预算内。
- [ ] 5. 新术语已进 [docs/glossary.md](glossary.md) 与 [scripts/terms.json](../scripts/terms.json)，两边顺序一致。
- [ ] 6. 每个 `references/*.md` 在 `SKILL.md` 中恰好被链接一次。
- [ ] 7. 体检表若变化，ADR 0005 与全部用例的 `review` 已同步。
- [ ] 8. `description` 若变化，[evals/router_cases.yaml](../evals/router_cases.yaml) 已同步。
- [ ] 9. `CHANGELOG.md` 有对应版本条目；破坏性变更写了 Migration。
- [ ] 10. 同一事实没有被复制到第二个位置。

## 失败处理

| 现象 | 判断 | 动作 |
|---|---|---|
| 新用例失败，旧用例全过 | 正常：新用例抓住了缺口 | 继续步 3，改提示词直到新用例通过 |
| 新用例通过，旧用例退步 | 改动引入回归 | 回滚本次改动；先修退步项，再重放新用例 |
| 新旧用例都不动 | 判据没有观察行为 | 重写 `review` 或 `expect`，换成可观察量；不要改提示词 |
| 连续两次修不好 | 方案假设不成立 | 停手，写 ADR 记录被否决的方案、失败证据、下次尝试的判据 |
| gate 与人工判断冲突 | 规则与实现不一致 | 以 gate 为准改内容；确认 gate 本身错时，先改 `check.py` 与其自测，再改内容 |
| 预算接近上限 | 内容仍在增长 | 先搬迁到 `references/`，再压缩，最后才提上限并在变更记录说明 |

回滚用 `git revert` 保留证据，不用 `reset --hard`。被否决的方案写进 ADR 的「备选方案」，同时写清它为什么会失败：这是下一次维护者唯一能复用的信息。
