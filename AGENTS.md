# AGENTS.md

本仓库把 skill 提示词当作生产代码维护：运行时入口是 [SKILL.md](SKILL.md)，理由与诊断在 [docs/design.md](docs/design.md)，可检查的规则由 `scripts/check.py` 执行。改任何行为前先读 [docs/authoring.md](docs/authoring.md)。

## 命令

| 命令 | 作用 |
|---|---|
| `python3 scripts/check.py --all` | 运行全部 8 个结构 gate；提交前必须通过 |
| `python3 scripts/check.py --only <id>` | 只跑一个 gate，用于定位 |
| `python3 scripts/check.py --list` | 列出 gate id 与一行说明 |
| `python3 scripts/test_gates.py` | 逐条破坏规则，确认对应 gate 会失败；改过门禁后必须跑 |

## 唯一事实源

| 事实 | 家 |
|---|---|
| 运行时指令、类型门禁表、三闸、AI 味六项、体检表 | [SKILL.md](SKILL.md) |
| 理由、四症状因果链、五条设计原则、非目标 | [docs/design.md](docs/design.md) |
| 版本语义、六步流程、变更影响矩阵、评审清单 | [docs/authoring.md](docs/authoring.md) |
| gate 清单、预算、测试破坏法、机器与人工分工 | [docs/verification.md](docs/verification.md) |
| 术语定义与禁用替代词 | [docs/glossary.md](docs/glossary.md) |
| 决策与被否决的备选方案 | [docs/decisions/](docs/decisions/) |
| 机器可读的术语与禁用词 | `scripts/terms.json` |

同一事实只写一处，其他位置只链接。

## 硬规则

1. 入口状态永远是「未判」，类型只能是 P0 探针的输出（[SKILL.md](SKILL.md) §1）。
2. 一个文件只承载一种文档类型；出现第二种就拆或删，不改标题敷衍（[SKILL.md](SKILL.md) §2）。
3. 骨架不过不展开正文：首段没有可反驳的一句话结论，就先补结论（[SKILL.md](SKILL.md) §3）。
4. 写完必须按五个判据删，删减节数与段数写进体检表（[SKILL.md](SKILL.md) §4、§7）。
5. 新术语先写 [docs/glossary.md](docs/glossary.md)，再同步 `scripts/terms.json` 的 `terms` 与 `forbidden`，最后才在正文使用。
6. 改门禁、类型集合或体检表字段时，先加或改用例，再改 [SKILL.md](SKILL.md)，最后同步参考文件与文档（[docs/authoring.md](docs/authoring.md)）。
7. 报告层缺任何一行即未完成；体检表只写在对话报告里，不写进文档正文（[SKILL.md](SKILL.md) §7）。
8. 预算超限按 搬迁 → 压缩 → 提上限 的顺序处理，提上限必须在变更记录写明理由（[docs/verification.md](docs/verification.md)）。
9. `check.py --all` 未通过不提交（[docs/verification.md](docs/verification.md)）。
10. 版本号只升 patch 或 minor；major 只在用户明确要求时升，不得用 minor 伪装（[docs/authoring.md](docs/authoring.md#版本语义)）。
11. `major` 变更必须在 [CHANGELOG.md](CHANGELOG.md) 的 Migration 段说明旧文档怎么迁移。
12. 新增 ADR 必须被 [docs/design.md](docs/design.md) 的决策记录表链接；没有 gate 检查这一条，由人工评审保证。
13. 理由不写进 `SKILL.md`；理由进 [docs/design.md](docs/design.md) 或 ADR，入口只写动作。
14. 每条新规则至少被一个 gate 或一条用例命中；不可测的规则会在下一次改动时静默失效。
15. `evals/` 不参与自动测试：只有用户明确要求时才手动运行用例，`check`、`test-gates`、pre-commit 与 CI 都不跑它；结果只在本机记录，不回写仓库。

## 编辑本文件

只放每次会话都必须知道的常驻规则，每条 1 到 3 行，细节链接到唯一事实源。超限时先搬迁，再压缩，最后才提上限并在变更记录说明。

## 机器检查与人工评审

| 检查方式 | 覆盖 |
|---|---|
| `check.py --all`（每次提交） | frontmatter、sections、refs、forbidden_words、terms、budget、checklist、link_targets，共 8 个 gate |
| `test_gates.py`（门禁改动） | 破坏每条规则，确认对应 gate 会失败，防止静默通过 |
| 人工评审（发布前） | 用例输出、文档类型判得对不对、一句话结论是否可反驳、删减是否真的发生、触发判断 |
| 人工抽样（不定期） | 真实调用记录里的漏触发与误触发 |
