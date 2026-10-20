#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识库一致性检查

设计文档把「每月一致性检查」列为防止知识库腐化的三条机制之一，但一直没有实现。
这个脚本就是它。

它检查的是**跨文件的接缝**——单看每个文件都没问题、拼起来才暴露的那类问题。
2026-10-20 的一次端到端演练发现，全套体系的卡点几乎全部落在这种接缝上：
`STD-BASE-104` 被 5 处引用却根本没有定义；文档写着「未实现」而 Skill 早已实现。
这类问题的共同点是**单文件检查发现不了**。

用法：
  python3 00_工作空间配置/scripts/consistency_check.py
  python3 00_工作空间配置/scripts/consistency_check.py --json

退出码：0 无问题 ｜ 1 有问题 ｜ 2 脚本自身出错
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("错误：缺少 PyYAML。安装：pip install pyyaml\n")
    sys.exit(2)

# 示例标记：只放**明确表示"这是举例"**的词。
# 不要把「格式」「建议」这类正文常用词放进来——第一版放了，结果一行写着
# 「**格式**不可随意改动」的正文被当成示例，真实悬空引用反而被跳过。
EXAMPLE_MARKERS = ("示例", "例：", "例如", "参考形态", "占位", "待填")

# 反例与提议只影响「Skill 名引用」的检查口径（那里确实有大量故意举的错名）
SKILL_REF_MARKERS = EXAMPLE_MARKERS + ("反例", "反模式", "别扭", "建议", "会得到")

# 提案类文档：设计文档与演练记录通篇是假设的编号与假想的反例，不参与引用检查。
# 它们记录的是「可以长什么样」与「曾经是什么样」，不是当前事实。
PROPOSAL_DOCS = ("docs/",)


def is_proposal(f: Path, root: Path) -> bool:
    return f.relative_to(root).as_posix().startswith(PROPOSAL_DOCS)
STD_RE = re.compile(r"STD-[A-Z0-9]+-\d{3}")
SKILL_RE = re.compile(r"`(ai-[a-z0-9-]+)`")
SKILL_DIR_RE = re.compile(r"^(gate-\d{2})-")
STAGE = {"requirement", "design", "dev", "test", "iteration", "daily",
         "gate", "archive", "spec"}
TOOL_SUFFIX = ("-autopilot", "-runner", "-convert")


def find_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "CLAUDE.md").is_file() and (p / "09_资产库").is_dir():
            return p
    raise SystemExit("未找到仓库根目录")


def md_files(root: Path, include_proposals: bool = False):
    for f in sorted(root.rglob("*.md")):
        if ".git" in f.parts or f.relative_to(root).as_posix().startswith("projects/"):
            continue
        if not include_proposals and is_proposal(f, root):
            continue
        yield f


def is_separator(line: str) -> bool:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return bool(cells) and all(set(c) <= set("-: ") for c in cells if c) and any(cells)


def ref_lines(f: Path, markers=EXAMPLE_MARKERS):
    """逐行产出 (行号, 行内容, 是否示例)。

    「示例」常常写在**表头**而不是数据行（如 `| 层级 | 前缀 | 示例 |`），
    所以按「该行所属表格的表头」判定，而不是只看本行。
    """
    lines = f.read_text(encoding="utf-8").split("\n")
    header = ""
    for i, line in enumerate(lines):
        if line.lstrip().startswith("|") and i + 1 < len(lines) and is_separator(lines[i + 1]):
            header = line
        example = any(m in line for m in markers) or any(m in header for m in markers)
        yield i + 1, line, example


# ── 检查 1：STD 条目的悬空引用 ────────────────────────────────

def check_std_refs(root: Path):
    defined = set()
    sources = list(root.glob("*/standards/*.md")) + [
        p for p in (root / "09_资产库" / "规范包").rglob("*.md") if p.name != "PACK.md"]
    for f in sources:
        defined |= set(re.findall(r"^## (STD-[A-Z0-9-]+)",
                                  f.read_text(encoding="utf-8"), re.M))
    problems, refs = [], set()
    for f in md_files(root):
        for _, line, example in ref_lines(f):
            if example:
                continue
            for sid in STD_RE.findall(line):
                refs.add(sid)
                if sid not in defined:
                    problems.append({
                        "kind": "std-dangling",
                        "detail": f"{sid} 被引用但无定义",
                        "where": f"{f.relative_to(root)}: {line.strip()[:70]}",
                    })
    return problems, len(defined), len(refs)


# ── 检查 2：Skill 名引用有效性 ────────────────────────────────

def check_skill_refs(root: Path):
    names = {p.parent.name for p in root.rglob("SKILL.md")}
    problems = []
    for f in md_files(root):
        for _, line, example in ref_lines(f, SKILL_REF_MARKERS):
            if example:
                continue
            for n in SKILL_RE.findall(line):
                if n in names or n.startswith("ai-spec-effective"):
                    continue
                # 允许 `ai-test-04` 这类省略后缀的短形式（前缀匹配唯一即算有效）
                if any(x.startswith(n + "-") for x in names):
                    continue
                problems.append({"kind": "skill-ref",
                                 "detail": f"`{n}` 不是已存在的 Skill 名",
                                 "where": f"{f.relative_to(root)}: {line.strip()[:70]}"})
    return problems, len(names)


# ── 检查 3：三件套与 frontmatter ──────────────────────────────

def check_skills(root: Path):
    problems = []
    paths = sorted(root.rglob("SKILL.md"))
    for p in paths:
        d = p.parent
        try:
            meta = yaml.safe_load(p.read_text(encoding="utf-8").split("---")[1])
        except Exception as e:
            problems.append({"kind": "frontmatter", "detail": f"解析失败：{e}",
                             "where": str(p.relative_to(root))})
            continue
        if meta.get("name") != d.name:
            problems.append({"kind": "frontmatter",
                             "detail": f"name={meta.get('name')} 与目录名 {d.name} 不一致",
                             "where": str(p.relative_to(root))})
        for k in ("version", "stage", "owner", "updated", "status"):
            if k not in meta:
                problems.append({"kind": "frontmatter",
                                 "detail": f"frontmatter 缺 `{k}`",
                                 "where": str(p.relative_to(root))})
        tail = d.name[3:] if d.name.startswith("ai-") else ""
        if tail and not tail.endswith(TOOL_SUFFIX) and tail.split("-")[0] not in STAGE:
            problems.append({"kind": "naming",
                             "detail": f"域前缀 `{tail.split('-')[0]}` 不在枚举内",
                             "where": d.name})
        for f in ("prompt.md", "references/INDEX.md"):
            if not (d / f).exists():
                problems.append({"kind": "trinity", "detail": f"缺 {f}",
                                 "where": str(d.relative_to(root))})
    return problems, len(paths)


# ── 检查 4：上下文预算 ────────────────────────────────────────

BUDGET = {("CLAUDE.md", None): 200,
          ("SKILL.md", None): 150,
          ("prompt.md", None): 300}


def check_budget(root: Path):
    problems = []
    for f in root.rglob("*"):
        if not f.is_file() or f.name not in ("CLAUDE.md", "SKILL.md", "prompt.md"):
            continue
        if ".git" in f.parts:
            continue
        limit = next(v for (n, _), v in BUDGET.items() if n == f.name)
        lines = len(f.read_text(encoding="utf-8").split("\n"))
        if lines > limit:
            problems.append({"kind": "budget",
                             "detail": f"{lines} 行，超出 {limit} 行预算",
                             "where": str(f.relative_to(root))})
    return problems


# ── 检查 5：门禁引用的检查项都有实现 ──────────────────────────

def check_gates(root: Path):
    script = root / "07_质量门禁/skills/ai-gate-runner/scripts/gate_run.py"
    if not script.is_file():
        return [{"kind": "gate", "detail": "找不到 gate_run.py", "where": "-"}], 0
    impl = set(re.findall(r'@check\("([a-z0-9-]+)"', script.read_text(encoding="utf-8")))
    used = set()
    for g in sorted((root / "07_质量门禁/gates").glob("gate-*.md")):
        used |= set(re.findall(r"auto:([a-z0-9-]+)", g.read_text(encoding="utf-8")))
    problems = [{"kind": "gate", "detail": f"门禁引用了未实现的检查项 `{c}`", "where": "gates/"}
                for c in sorted(used - impl)]
    return problems, len(used)


# ── 检查 6：文档里的状态描述与 frontmatter 是否矛盾 ───────────

def check_status_claims(root: Path):
    """文档写「未实现」而 frontmatter 已 implemented（或反之）——演练发现的 C-05 属于这一类。"""
    problems = []
    for p in sorted(root.rglob("SKILL.md")):
        try:
            meta = yaml.safe_load(p.read_text(encoding="utf-8").split("---")[1])
        except Exception:
            continue
        status = meta.get("status")
        body = p.read_text(encoding="utf-8")
        if status == "implemented" and "本 Skill 未实现" in body:
            problems.append({"kind": "status-claim",
                             "detail": "status 是 implemented，正文却写着「本 Skill 未实现」",
                             "where": str(p.relative_to(root))})
        if status == "not_implemented" and "本 Skill 已实现" in body:
            problems.append({"kind": "status-claim",
                             "detail": "status 是 not_implemented，正文却写着「已实现」",
                             "where": str(p.relative_to(root))})
    # 全局状态段：写「未实现」而该域已全部实现（只在非提案文档里查）
    for f in md_files(root):
        txt = f.read_text(encoding="utf-8")
        for m in re.finditer(r"(尚未就位|不要调用该域的 Skill)[^\n]{0,40}(`0[2-6]`)", txt):
            problems.append({"kind": "status-claim",
                             "detail": "全局状态描述声称某域尚未就位（演练发现这类描述极易过期）",
                             "where": str(f.relative_to(root))})
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="知识库一致性检查")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--repo", help="仓库根目录")
    args = ap.parse_args()

    root = Path(args.repo).resolve() if args.repo else find_root(Path(__file__).resolve())

    all_problems = []
    p1, n_def, n_ref = check_std_refs(root)
    p2, n_skill = check_skill_refs(root)
    p3, n_skillmd = check_skills(root)
    p4 = check_budget(root)
    p5, n_gate_checks = check_gates(root)
    p6 = check_status_claims(root)
    all_problems = p1 + p2 + p3 + p4 + p5 + p6

    if args.json:
        print(json.dumps({"problems": all_problems,
                          "stats": {"std_defined": n_def, "std_referenced": n_ref,
                                    "skills": n_skill, "gate_checks": n_gate_checks}},
                         ensure_ascii=False, indent=2))
        return 1 if all_problems else 0

    groups = {
        "std-dangling": "STD 条目悬空引用",
        "skill-ref": "Skill 名引用无效",
        "frontmatter": "SKILL.md 元信息",
        "naming": "Skill 命名",
        "trinity": "三件套缺失",
        "budget": "上下文预算超标",
        "gate": "门禁检查项",
        "status-claim": "状态描述与实现矛盾",
    }
    print(f"\n知识库一致性检查")
    print(f"  STD 条目 {n_def} 个（被引用 {n_ref} 个）｜ Skill {n_skill} 个 ｜ "
          f"门禁检查项 {n_gate_checks} 个\n")
    if not all_problems:
        print("  ✅ 未发现跨文件不一致\n")
        return 0
    for kind, label in groups.items():
        items = [x for x in all_problems if x["kind"] == kind]
        if not items:
            continue
        print(f"  ❌ {label}（{len(items)} 处）")
        for x in items[:12]:
            print(f"     {x['detail']}\n       {x['where']}")
        if len(items) > 12:
            print(f"     …另有 {len(items) - 12} 处")
        print()
    print(f"  合计 {len(all_problems)} 处。\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())