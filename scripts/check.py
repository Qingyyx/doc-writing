#!/usr/bin/env python3
"""doc-writing 结构门禁。

每个 gate 是一个函数，接收 Repo 并返回 Failure 列表；空列表表示通过。
gate 注册在 GATES 中，带 id 与一行说明。

用法：
    python3 scripts/check.py --all      # 运行全部 gate（默认）
    python3 scripts/check.py --list     # 打印 gate 清单
    python3 scripts/check.py --only ID  # 只运行一个 gate
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


# 事实源与版本文件
SKILL_REL = "SKILL.md"
VERSION_REL = "VERSION"
SKILL_ID = "doc-writing"

# 二级标题：交付物 + 9 个编号节，共 10 个，顺序固定。
# 每项是要在第 N 个二级标题里出现的文字片段。
EXPECTED_SECTIONS = (
    "交付物",
    "入口：目的未判",
    "五种文档，五道门禁",
    "结构闸：结论前置",
    "删减闸：写完必须删",
    "AI 味六项",
    "实例化",
    "输出契约",
    "硬性禁止",
    "按需加载",
)

# references 下应有恰好 7 个 .md，且每个相对路径在 SKILL.md 中出现恰好一次。
EXPECTED_REF_COUNT = 7

# 输出契约一节体检表必须包含的字段名。
CHECKLIST_FIELDS = (
    "类型",
    "一句话结论",
    "读者与决定",
    "删减",
    "证据强度",
    "未验证",
    "私有条件缺口",
)

# 文档自身行文里的模糊词。
FORBIDDEN_WORDS = (
    "视情况",
    "酌情",
    "尽量",
    "根据需要",
    "值得注意的是",
    "本文将讨论",
)

# “随着……的发展”属于同一句内的组合禁用模式。
FORBIDDEN_PATTERNS = (
    (re.compile(r"随着[^。\n]{0,30}?的发展"), "随着…的发展"),
)

# 匹配 SKILL.md 里所有 references/xxx.md 形式的目标。
REF_PATH_RE = re.compile(r"references/[A-Za-z0-9_.\-/]+\.md")

# 引号包裹的片段通常是“反例引用”，扫描禁用词时按数据屏蔽掉。
QUOTE_RE = re.compile(r'"[^"\n]*"|“[^”\n]*”|「[^」\n]*」|『[^』\n]*』')


@dataclass(frozen=True)
class Failure:
    """一条门禁失败记录：具体位置 + 修复建议。"""

    message: str
    fix: str


class Repo:
    """只读的地盘模型，缓存文件文本，避免重复读盘。"""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._text: dict[str, str | None] = {}

    def text(self, rel: str) -> str | None:
        """读取文件文本；不存在或不是 UTF-8 时返回 None。"""
        if rel not in self._text:
            try:
                self._text[rel] = (self.root / rel).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                self._text[rel] = None
        return self._text[rel]

    def ref_files(self) -> list[Path]:
        """references/ 下的所有 .md 文件，按路径排序。"""
        directory = self.root / "references"
        if not directory.is_dir():
            return []
        return sorted(path for path in directory.glob("*.md") if path.is_file())

    def ref_rels(self) -> list[str]:
        """references 下 .md 的相对路径（POSIX 形式）。"""
        return [path.relative_to(self.root).as_posix() for path in self.ref_files()]


# ---------------------------------------------------------------------------
# 通用文本工具
# ---------------------------------------------------------------------------


def blank_non_newline(text: str) -> str:
    """把非换行字符替换为空格，保留行号与长度。"""
    return re.sub(r"[^\n]", " ", text)


def mask_inline_code(line: str) -> str:
    """把行内 `code` 片段替换为等长空格。"""
    chars = list(line)
    i = 0
    while i < len(line):
        if line[i] != "`":
            i += 1
            continue
        j = i
        while j < len(line) and line[j] == "`":
            j += 1
        ticks = line[i:j]
        close = line.find(ticks, j)
        if close == -1:
            i = j
            continue
        for pos in range(i, close + len(ticks)):
            if chars[pos] != "\n":
                chars[pos] = " "
        i = close + len(ticks)
    return "".join(chars)


def fence_marker(line: str) -> tuple[str, int, str] | None:
    """识别代码围栏行；返回 (围栏字符, 长度, 尾部内容)。"""
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3:
        return None
    match = re.match(r"^(`{3,}|~{3,})(.*)$", stripped.rstrip("\r\n"))
    if not match:
        return None
    marker = match.group(1)
    rest = match.group(2)
    if marker[0] == "`" and "`" in rest:
        return None
    return marker[0], len(marker), rest


def mask_code(text: str) -> str:
    """屏蔽围栏代码块与行内代码，保留换行以便回溯行号。"""
    out: list[str] = []
    fence: tuple[str, int] | None = None
    for line in text.splitlines(keepends=True):
        marker = fence_marker(line)
        if fence is not None:
            out.append(blank_non_newline(line))
            if (
                marker is not None
                and marker[0] == fence[0]
                and marker[1] >= fence[1]
                and marker[2].strip() == ""
            ):
                fence = None
            continue
        if marker is not None:
            fence = (marker[0], marker[1])
            out.append(blank_non_newline(line))
            continue
        out.append(mask_inline_code(line))
    return "".join(out)


def scan_text(text: str) -> str:
    """禁用词扫描用的视图：代码与引号内容都视为数据。"""
    return QUOTE_RE.sub(lambda m: blank_non_newline(m.group(0)), mask_code(text))


def line_at(masked: str, index: int) -> int:
    """由字符下标回推 1 起的行号。"""
    return masked.count("\n", 0, index) + 1


def first_line_with(text: str, needle: str) -> int:
    """原文本中首次出现某子串的行号；找不到返回 1。"""
    index = text.find(needle)
    if index < 0:
        return 1
    return text.count("\n", 0, index) + 1


def iter_headings(text: str):
    """逐行产出 (行号, 级别, 标题文字)，跳过代码围栏内的伪标题。"""
    fence: tuple[str, int] | None = None
    for lineno, line in enumerate(text.splitlines(), 1):
        marker = fence_marker(line)
        if fence is not None:
            if (
                marker is not None
                and marker[0] == fence[0]
                and marker[1] >= fence[1]
                and marker[2].strip() == ""
            ):
                fence = None
            continue
        if marker is not None:
            fence = (marker[0], marker[1])
            continue
        match = re.match(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if match:
            yield lineno, len(match.group(1)), match.group(2).strip()


# ---------------------------------------------------------------------------
# frontmatter 解析（只覆盖本 skill 需要的 YAML 子集）
# ---------------------------------------------------------------------------


def split_frontmatter(text: str) -> tuple[str | None, str, str]:
    """拆出 frontmatter 原文与正文；返回 (raw, body, error)。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text, "文件不以 --- 开头"
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        return None, text, "frontmatter 缺少结束的 ---"
    return "\n".join(lines[1:end]), "\n".join(lines[end + 1 :]), ""


def clean_scalar(value: str) -> str:
    """去掉标量两侧空白与成对引号。"""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def parse_yaml_subset(raw: str) -> dict:
    """解析缩进式 YAML 子集：映射 + 标量 + 列表。

    不支持锚点、多行标量、流式集合等语法；遇到无法解析的结构时抛出
    ValueError，并带上原始行号。
    """
    entries: list[tuple[int, int, str]] = []
    for offset, line in enumerate(raw.splitlines()):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        entries.append((offset + 2, indent, line.strip()))
    if not entries:
        return {}
    if entries[0][1] != 0:
        raise ValueError(f"第 {entries[0][0]} 行缩进必须为 0")
    value, index = parse_block(entries, 0, 0)
    if index != len(entries):
        raise ValueError(f"第 {entries[index][0]} 行无法归属到任何层级")
    return value


def parse_block(entries: list[tuple[int, int, str]], index: int, indent: int):
    """解析同一缩进下的一个块，返回 (值, 下一个待处理下标)。"""
    if entries[index][2].startswith("- "):
        items: list[str] = []
        while (
            index < len(entries)
            and entries[index][1] == indent
            and entries[index][2].startswith("- ")
        ):
            items.append(clean_scalar(entries[index][2][2:]))
            index += 1
        return items, index

    result: dict[str, object] = {}
    while index < len(entries):
        lineno, current_indent, content = entries[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(f"第 {lineno} 行缩进异常: {content!r}")
        if ":" not in content:
            raise ValueError(f"第 {lineno} 行缺少冒号: {content!r}")
        key, _, value = content.partition(":")
        key = key.strip()
        value = value.strip()
        index += 1
        if value:
            result[key] = clean_scalar(value)
            continue
        # 值为空：下面是缩进更深的块，或同缩进的列表项。
        if index < len(entries) and (
            entries[index][1] > indent
            or (entries[index][1] == indent and entries[index][2].startswith("- "))
        ):
            child, index = parse_block(entries, index, entries[index][1])
            result[key] = child
        else:
            result[key] = None
    return result, index


def frontmatter_key_line(raw: str, key: str, indent: int) -> int:
    """在 frontmatter 原文里定位某个 key 的行号（frontmatter 从文件第 2 行起）。"""
    prefix = " " * indent + key + ":"
    for offset, line in enumerate(raw.splitlines()):
        if line.startswith(prefix):
            return offset + 2
    return 2


# ---------------------------------------------------------------------------
# JSON 读取
# ---------------------------------------------------------------------------


def load_json(repo: Repo, rel: str) -> tuple[object | None, Failure | None]:
    """读取并解析 JSON；缺失或损坏时返回可展示的 Failure。"""
    text = repo.text(rel)
    if text is None:
        return None, Failure(
            f"{rel}:1 文件不存在或不是 UTF-8",
            f"创建 {rel}；然后运行 python3 scripts/check.py --all",
        )
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, Failure(
            f"{rel}:{exc.lineno} JSON 解析失败: {exc.msg}",
            f"修正 {rel} 的 JSON 语法；然后运行 python3 scripts/check.py --all",
        )


# ---------------------------------------------------------------------------
# 门禁实现
# ---------------------------------------------------------------------------


def gate_frontmatter(repo: Repo) -> list[Failure]:
    """SKILL.md frontmatter 必备字段、name 与版本一致性。"""
    fix = "python3 scripts/check.py --only frontmatter"
    skill = repo.text(SKILL_REL)
    if skill is None:
        return [Failure(f"{SKILL_REL}:1 文件不存在或不是 UTF-8", f"创建 {SKILL_REL}；然后运行 {fix}")]

    raw, _, error = split_frontmatter(skill)
    if raw is None:
        return [Failure(f"{SKILL_REL}:1 frontmatter 解析失败: {error}", f"修正 frontmatter；然后运行 {fix}")]
    try:
        meta = parse_yaml_subset(raw)
    except ValueError as exc:
        return [Failure(f"{SKILL_REL}:1 frontmatter 解析失败: {exc}", f"修正 frontmatter；然后运行 {fix}")]
    if not isinstance(meta, dict):
        return [Failure(f"{SKILL_REL}:1 frontmatter 必须是映射", f"修正 frontmatter；然后运行 {fix}")]

    failures: list[Failure] = []

    name = meta.get("name")
    if name != SKILL_ID:
        failures.append(
            Failure(
                f"{SKILL_REL}:{frontmatter_key_line(raw, 'name', 0)} name={name!r}，必须为 {SKILL_ID!r}",
                f"把 name 改为 {SKILL_ID}；然后运行 {fix}",
            )
        )

    description = meta.get("description")
    if not isinstance(description, str) or not description.strip():
        failures.append(
            Failure(
                f"{SKILL_REL}:{frontmatter_key_line(raw, 'description', 0)} description 缺失或为空",
                f"补上非空 description；然后运行 {fix}",
            )
        )

    metadata = meta.get("metadata")
    if not isinstance(metadata, dict):
        failures.append(
            Failure(
                f"{SKILL_REL}:{frontmatter_key_line(raw, 'metadata', 0)} metadata 缺失或不是映射",
                f"补上 metadata 映射；然后运行 {fix}",
            )
        )
        return failures

    version = metadata.get("version")
    category = metadata.get("category")
    tags = metadata.get("tags")

    if not isinstance(version, str) or not version:
        failures.append(
            Failure(
                f"{SKILL_REL}:{frontmatter_key_line(raw, 'version', 2)} metadata.version 缺失",
                f"补上 metadata.version；然后运行 {fix}",
            )
        )
    else:
        version_text = repo.text(VERSION_REL)
        if version_text is None:
            failures.append(
                Failure(f"{VERSION_REL}:1 文件不存在或不是 UTF-8", f"创建 {VERSION_REL}；然后运行 {fix}")
            )
        else:
            expected = version_text.strip()
            if version != expected:
                failures.append(
                    Failure(
                        f"{SKILL_REL}:{frontmatter_key_line(raw, 'version', 2)} metadata.version={version!r} 与 VERSION={expected!r} 不一致",
                        f"同步两处版本号；然后运行 {fix}",
                    )
                )

    if not isinstance(category, str) or not category:
        failures.append(
            Failure(
                f"{SKILL_REL}:{frontmatter_key_line(raw, 'category', 2)} metadata.category 缺失",
                f"补上 metadata.category；然后运行 {fix}",
            )
        )

    if not isinstance(tags, list) or not tags:
        failures.append(
            Failure(
                f"{SKILL_REL}:{frontmatter_key_line(raw, 'tags', 2)} metadata.tags 必须是非空列表",
                f"补上 metadata.tags 列表；然后运行 {fix}",
            )
        )
    return failures


def gate_sections(repo: Repo) -> list[Failure]:
    """二级标题数量、顺序与文字。"""
    fix = "python3 scripts/check.py --only sections"
    skill = repo.text(SKILL_REL)
    if skill is None:
        return [Failure(f"{SKILL_REL}:1 文件不存在或不是 UTF-8", f"创建 {SKILL_REL}；然后运行 {fix}")]

    headings = [(lineno, text) for lineno, level, text in iter_headings(skill) if level == 2]
    actual = [text for _, text in headings]
    expected_count = len(EXPECTED_SECTIONS)
    if len(headings) != expected_count:
        return [
            Failure(
                f"{SKILL_REL}:1 二级标题应为 {expected_count} 个（交付物 + 9 个编号节），实际 {len(headings)} 个: {actual}",
                f"按 SKILL.md 目录结构调整 ## 标题；然后运行 {fix}",
            )
        ]

    failures: list[Failure] = []
    for index, fragment in enumerate(EXPECTED_SECTIONS):
        lineno, text = headings[index]
        if fragment not in text:
            failures.append(
                Failure(
                    f"{SKILL_REL}:{lineno} 第 {index + 1} 个二级标题应含「{fragment}」，实际「{text}」",
                    f"按顺序修正该标题；当前全部标题: {actual}；然后运行 {fix}",
                )
            )
    return failures


def gate_refs(repo: Repo) -> list[Failure]:
    """references 数量与 SKILL.md 中的引用次数。"""
    fix = "python3 scripts/check.py --only refs"
    skill = repo.text(SKILL_REL)
    if skill is None:
        return [Failure(f"{SKILL_REL}:1 文件不存在或不是 UTF-8", f"创建 {SKILL_REL}；然后运行 {fix}")]

    rels = repo.ref_rels()
    failures: list[Failure] = []
    if len(rels) != EXPECTED_REF_COUNT:
        failures.append(
            Failure(
                f"references/:1 期望恰好 {EXPECTED_REF_COUNT} 个 .md 文件，实际 {len(rels)} 个: {rels or '（空）'}",
                f"补齐或删除 references/*.md，使其为 {EXPECTED_REF_COUNT} 个；然后运行 {fix}",
            )
        )
    for rel in rels:
        count = skill.count(rel)
        if count != 1:
            failures.append(
                Failure(
                    f"{rel}:1 在 SKILL.md 中被引用 {count} 次，必须恰好 1 次",
                    f"在 SKILL.md「按需加载」表中只保留一处 {rel}；然后运行 {fix}",
                )
            )
    return failures


def gate_forbidden_words(repo: Repo) -> list[Failure]:
    """SKILL.md 与 references 不得出现模糊词（引号反例与代码块除外）。"""
    fix = "python3 scripts/check.py --only forbidden_words"
    failures: list[Failure] = []
    targets = [SKILL_REL, *repo.ref_rels()]

    for rel in targets:
        text = repo.text(rel)
        if text is None:
            failures.append(Failure(f"{rel}:1 文件不存在或不是 UTF-8", f"确认文件可读；然后运行 {fix}"))
            continue
        masked = scan_text(text)
        for word in FORBIDDEN_WORDS:
            index = masked.find(word)
            if index != -1:
                failures.append(
                    Failure(
                        f"{rel}:{line_at(masked, index)} 出现禁用词「{word}」",
                        f"删除该词或改成可判定表述；然后运行 {fix}",
                    )
                )
        for pattern, label in FORBIDDEN_PATTERNS:
            match = pattern.search(masked)
            if match:
                failures.append(
                    Failure(
                        f"{rel}:{line_at(masked, match.start())} 出现禁用组合「{label}」",
                        f"删掉该句式，直接从事实开始；然后运行 {fix}",
                    )
                )
    return failures


def gate_terms(repo: Repo) -> list[Failure]:
    """terms.json 规定的必现术语与禁用词。"""
    fix = "python3 scripts/check.py --only terms"
    data, error = load_json(repo, "scripts/terms.json")
    if error is not None:
        return [error]
    if not isinstance(data, dict):
        return [Failure("scripts/terms.json:1 顶层必须是对象", f"改成 {{\"terms\": [...], \"forbidden\": [...]}}；然后运行 {fix}")]

    terms = data.get("terms")
    forbidden = data.get("forbidden", [])
    if not isinstance(terms, list) or not all(isinstance(item, str) and item for item in terms):
        return [Failure("scripts/terms.json:1 terms 必须是非空字符串列表", f"修正 terms 字段；然后运行 {fix}")]
    if not isinstance(forbidden, list) or not all(isinstance(item, str) and item for item in forbidden):
        return [Failure("scripts/terms.json:1 forbidden 必须是字符串列表", f"修正 forbidden 字段；然后运行 {fix}")]

    failures: list[Failure] = []
    skill = repo.text(SKILL_REL)
    if skill is None:
        return [Failure(f"{SKILL_REL}:1 文件不存在或不是 UTF-8", f"创建 {SKILL_REL}；然后运行 {fix}")]

    for term in terms:
        if term not in skill:
            failures.append(
                Failure(
                    f"{SKILL_REL}:1 术语「{term}」未在 SKILL.md 中出现",
                    f"在 SKILL.md 使用该术语，或从 scripts/terms.json 移除；然后运行 {fix}",
                )
            )

    targets = [SKILL_REL, *repo.ref_rels()]
    for rel in targets:
        text = repo.text(rel)
        if text is None:
            continue
        masked = scan_text(text)
        for word in forbidden:
            index = masked.find(word)
            if index != -1:
                failures.append(
                    Failure(
                        f"{rel}:{line_at(masked, index)} 出现 terms.json 禁用词「{word}」",
                        f"删掉该词或改用规范术语；然后运行 {fix}",
                    )
                )
    return failures


def gate_budget(repo: Repo) -> list[Failure]:
    """按 scripts/budget.json 检查行数与字符数。"""
    fix = "python3 scripts/check.py --only budget"
    data, error = load_json(repo, "scripts/budget.json")
    if error is not None:
        return [error]
    if not isinstance(data, dict):
        return [Failure("scripts/budget.json:1 顶层必须是对象", f"修正 schema；然后运行 {fix}")]

    limits: dict[str, int] = {}
    for key in ("skill_lines", "skill_chars", "reference_lines"):
        value = data.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            return [Failure(f"scripts/budget.json:1 {key} 必须是正整数", f"修正 {key}；然后运行 {fix}")]
        limits[key] = value

    failures: list[Failure] = []
    skill = repo.text(SKILL_REL)
    if skill is None:
        failures.append(Failure(f"{SKILL_REL}:1 文件不存在或不是 UTF-8", f"创建 {SKILL_REL}；然后运行 {fix}"))
    else:
        skill_lines = len(skill.splitlines())
        if skill_lines > limits["skill_lines"]:
            failures.append(
                Failure(
                    f"{SKILL_REL}:1 行数 {skill_lines} 超过预算 {limits['skill_lines']}",
                    f"删减 SKILL.md，或按流程提预算；然后运行 {fix}",
                )
            )
        skill_chars = len(skill)
        if skill_chars > limits["skill_chars"]:
            failures.append(
                Failure(
                    f"{SKILL_REL}:1 字符数 {skill_chars} 超过预算 {limits['skill_chars']}",
                    f"删减 SKILL.md，或按流程提预算；然后运行 {fix}",
                )
            )

    for rel in repo.ref_rels():
        text = repo.text(rel)
        if text is None:
            failures.append(Failure(f"{rel}:1 文件不存在或不是 UTF-8", f"确认文件可读；然后运行 {fix}"))
            continue
        ref_lines = len(text.splitlines())
        if ref_lines > limits["reference_lines"]:
            failures.append(
                Failure(
                    f"{rel}:1 行数 {ref_lines} 超过预算 {limits['reference_lines']}",
                    f"删减该 reference，或按流程提预算；然后运行 {fix}",
                )
            )
    return failures


def gate_checklist(repo: Repo) -> list[Failure]:
    """输出契约一节的体检表字段齐全。"""
    fix = "python3 scripts/check.py --only checklist"
    skill = repo.text(SKILL_REL)
    if skill is None:
        return [Failure(f"{SKILL_REL}:1 文件不存在或不是 UTF-8", f"创建 {SKILL_REL}；然后运行 {fix}")]

    headings = list(iter_headings(skill))
    start = None
    for lineno, level, text in headings:
        if level == 2 and "输出契约" in text:
            start = lineno
            break
    if start is None:
        return [Failure(f"{SKILL_REL}:1 找不到 ## 输出契约", f"补上输出契约一节；然后运行 {fix}")]

    end = len(skill.splitlines()) + 1
    for lineno, level, _ in headings:
        if lineno > start and level <= 2:
            end = lineno
            break

    lines = skill.splitlines()
    body = "\n".join(lines[start:end - 1])
    failures: list[Failure] = []
    for field in CHECKLIST_FIELDS:
        if f"{field}：" not in body:
            failures.append(
                Failure(
                    f"{SKILL_REL}:{start} 输出契约一节缺少体检表字段「{field}：」",
                    f"在体检表补上「{field}：」；然后运行 {fix}",
                )
            )
    return failures


def gate_link_targets(repo: Repo) -> list[Failure]:
    """SKILL.md 中 references/xxx.md 目标必须真实存在。"""
    fix = "python3 scripts/check.py --only link_targets"
    skill = repo.text(SKILL_REL)
    if skill is None:
        return [Failure(f"{SKILL_REL}:1 文件不存在或不是 UTF-8", f"创建 {SKILL_REL}；然后运行 {fix}")]

    targets = sorted(set(REF_PATH_RE.findall(skill)))
    if not targets:
        return [Failure(f"{SKILL_REL}:1 未找到任何 references/*.md 目标", f"在按需加载表补上引用；然后运行 {fix}")]

    failures: list[Failure] = []
    for rel in targets:
        if not (repo.root / rel).is_file():
            failures.append(
                Failure(
                    f"{SKILL_REL}:{first_line_with(skill, rel)} 目标文件不存在: {rel}",
                    f"创建 {rel}，或改成已存在的目标；然后运行 {fix}",
                )
            )
    return failures


# ---------------------------------------------------------------------------
# 注册与运行
# ---------------------------------------------------------------------------


GATES: tuple[tuple[str, str, object], ...] = (
    ("frontmatter", "SKILL.md frontmatter 字段、name、metadata 与 VERSION 一致", gate_frontmatter),
    ("sections", "SKILL.md 二级标题数量、顺序与文字", gate_sections),
    ("refs", "references 恰好 7 个 .md 且各在 SKILL.md 中出现一次", gate_refs),
    ("forbidden_words", "SKILL.md 与 references 无模糊词", gate_forbidden_words),
    ("terms", "terms.json 必现术语与禁用词", gate_terms),
    ("budget", "按 budget.json 检查行数与字符数", gate_budget),
    ("checklist", "输出契约体检表字段齐全", gate_checklist),
    ("link_targets", "SKILL.md 引用的 references 目标存在", gate_link_targets),
)


def gate_by_id(gate_id: str):
    """按 id 查 gate；找不到返回 None。"""
    for gate in GATES:
        if gate[0] == gate_id:
            return gate
    return None


def run_gates(repo: Repo, selected: list[tuple[str, str, object]]) -> int:
    """运行选中的 gate，逐个打印 PASS/FAIL，返回进程退出码。"""
    failed = 0
    passed = 0
    for gate_id, _, func in selected:
        try:
            failures = func(repo)
        except Exception as exc:  # 门禁自身出错也要变成可读失败，而不是静默通过
            failures = [
                Failure(
                    f"内部错误: {type(exc).__name__}: {exc}",
                    f"保留完整报错并运行 python3 scripts/check.py --only {gate_id}",
                )
            ]
        if failures:
            failed += 1
            print(f"FAIL {gate_id}")
            for failure in failures:
                print(f"  {failure.message}")
                print(f"    修复: {failure.fix}")
        else:
            passed += 1
            print(f"PASS {gate_id}")

    print()
    print(f"通过 {passed}/{len(selected)} 个 gate")
    if failed:
        print(f"{failed} 个 gate 失败；修复后重跑 python3 scripts/check.py --all")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="doc-writing 结构门禁",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--all", action="store_true", help="运行全部 gate（默认）")
    mode.add_argument("--list", action="store_true", help="列出 gate id 与一行说明")
    mode.add_argument("--only", metavar="ID", help="只运行一个 gate")
    parser.add_argument(
        "--root",
        metavar="PATH",
        default=str(Path(__file__).resolve().parents[1]),
        help="skill 根目录（默认取脚本所在目录的上一级）",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"FAIL setup: --root 不是目录: {root}", file=sys.stderr)
        return 2
    repo = Repo(root)

    if args.list:
        width = max(len(gate_id) for gate_id, _, _ in GATES)
        for gate_id, description, _ in GATES:
            print(f"{gate_id:<{width}}  {description}")
        return 0

    if args.only:
        gate = gate_by_id(args.only)
        if gate is None:
            print(
                f"FAIL setup: 未知 gate id {args.only!r}\n"
                f"  修复: 运行 python3 scripts/check.py --list 查看可用 id",
                file=sys.stderr,
            )
            return 2
        return run_gates(repo, [gate])

    return run_gates(repo, list(GATES))


if __name__ == "__main__":
    sys.exit(main())
