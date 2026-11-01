#!/usr/bin/env python3
"""门禁自测：在临时目录复制 skill，逐条破坏规则，确认对应 gate 失败。

设计：
1. 每次用例都在 /tmp 下的独立副本里进行，源目录只读。
2. 副本先补齐最小 fixtures（7 个 reference、terms.json），使基线通过。
3. 先验证基线该 gate 通过，再破坏规则并确认它失败。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REF_NAMES = (
    "kinds.md",
    "structure.md",
    "deletion.md",
    "slop.md",
    "evidence.md",
    "instantiate.md",
    "anti-patterns.md",
    "rewrite.md",
)

TERMS_FIXTURE = '{"terms": ["交付物"], "forbidden": ["绝不可能出现词"]}\n'


def build_copy(dest: Path) -> None:
    """复制 skill 到 dest，并写入自测所需的最小 fixtures。"""
    shutil.copytree(
        ROOT,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", ".git"),
    )
    ref_dir = dest / "references"
    ref_dir.mkdir(exist_ok=True)
    for old in ref_dir.glob("*.md"):
        old.unlink()
    for name in REF_NAMES:
        (ref_dir / name).write_text(f"# {name}\n", encoding="utf-8")
    (dest / "scripts" / "terms.json").write_text(TERMS_FIXTURE, encoding="utf-8")


def run_check(dest: Path, gate_id: str) -> subprocess.CompletedProcess[str]:
    """在副本里只运行指定 gate。"""
    return subprocess.run(
        [sys.executable, str(dest / "scripts" / "check.py"), "--only", gate_id],
        cwd=dest,
        capture_output=True,
        text=True,
    )


def rewrite(path: Path, old: str, new: str) -> None:
    """把文件里的 old 替换成 new；找不到就报错，避免用例空转。"""
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"用例无效：{path} 中找不到 {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def break_frontmatter(dest: Path) -> None:
    rewrite(dest / "SKILL.md", "name: doc-writing", "name: other-skill")


def break_sections(dest: Path) -> None:
    rewrite(dest / "SKILL.md", "\n## 9｜按需加载", "\n## 额外小节\n\n无\n\n## 9｜按需加载")


def break_refs(dest: Path) -> None:
    (dest / "references" / "extra.md").write_text("# extra\n", encoding="utf-8")


def break_forbidden_words(dest: Path) -> None:
    path = dest / "SKILL.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n视情况处理。\n", encoding="utf-8")


def break_terms(dest: Path) -> None:
    path = dest / "SKILL.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n绝不可能出现词。\n", encoding="utf-8")


def break_budget(dest: Path) -> None:
    (dest / "scripts" / "budget.json").write_text(
        '{"skill_lines": 5, "skill_chars": 9000, "reference_lines": 120}\n',
        encoding="utf-8",
    )


def break_checklist(dest: Path) -> None:
    rewrite(dest / "SKILL.md", "未验证；", "未核验；")


def break_link_targets(dest: Path) -> None:
    rewrite(dest / "SKILL.md", "references/kinds.md", "references/not-exist.md")


CASES = (
    ("frontmatter", break_frontmatter),
    ("sections", break_sections),
    ("refs", break_refs),
    ("forbidden_words", break_forbidden_words),
    ("terms", break_terms),
    ("budget", break_budget),
    ("checklist", break_checklist),
    ("link_targets", break_link_targets),
)


def main() -> int:
    failures = 0
    temp_root = Path(tempfile.mkdtemp(prefix="doc-writing-gates-"))
    try:
        for gate_id, breaker in CASES:
            dest = temp_root / gate_id
            build_copy(dest)

            baseline = run_check(dest, gate_id)
            if baseline.returncode != 0:
                failures += 1
                print(f"FAIL test {gate_id}: 基线未通过")
                print(baseline.stdout.rstrip())
                print(baseline.stderr.rstrip())
                continue

            try:
                breaker(dest)
            except SystemExit as exc:
                failures += 1
                print(f"FAIL test {gate_id}: {exc}")
                continue

            broken = run_check(dest, gate_id)
            if broken.returncode == 1:
                print(f"PASS test {gate_id}: 基线通过，破坏后失败")
            else:
                failures += 1
                print(f"FAIL test {gate_id}: 破坏后退出码 {broken.returncode}，应为 1")
                print(broken.stdout.rstrip())
                print(broken.stderr.rstrip())
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    print()
    print(f"通过 {len(CASES) - failures}/{len(CASES)} 个门禁自测")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
