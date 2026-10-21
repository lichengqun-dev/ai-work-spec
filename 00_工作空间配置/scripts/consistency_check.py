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
import hashlib
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
        rel = f.relative_to(root).as_posix()
        if ".git" in f.parts or rel.startswith("projects/") or rel.startswith(".claude/"):
            continue
        if not include_proposals and is_proposal(f, root):
            continue
        yield f


def skill_md_files(root: Path):
    """知识库里的真实 SKILL.md。

    **排除 `.claude/skills/`** —— 那是生成的挂载层（只有 name+description），
    由 check_mount_layer 单独校验它与真实定义是否同步。
    不排除的话，挂载层会因为「缺 version/stage/owner」被误报成 37×5 处问题。
    """
    for p in sorted(root.rglob("SKILL.md")):
        parts = p.relative_to(root).parts
        if parts[0] in (".git", ".claude", "projects"):
            continue
        yield p


def is_separator(line: str) -> bool:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return bool(cells) and all(set(c) <= set("-: ") for c in cells if c) and any(cells)


# 转义竖线 `\|`：表格单元格里合法地嵌入一个字面竖线的写法。
# 不先屏蔽它，列数统计会被撑大——`| 表头 \| 编号 \| 级别 \|` 这种单元格会被算成多列。
_ESCAPED_PIPE = "\x00"


def table_cols(line: str) -> int:
    return len(line.replace(r"\|", _ESCAPED_PIPE).strip().strip("|").split("|"))


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


def fenced_mask(lines: list[str]) -> list[bool]:
    """标记每一行是否落在围栏代码块内（含围栏本身）。

    围栏里的内容常常是**格式演示**——比如 `09_资产库/规范包/INDEX.md` 用一段
    ```markdown 演示条目该怎么写，里面有一行 `## STD-VUE3-001 · …`。
    不屏蔽的话它会被当成真实条目定义：既虚增定义数，又可能把示例编号当成"已定义"
    从而漏掉真正的悬空引用。
    """
    inside, mask = False, []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            mask.append(True)          # 围栏行本身也算
            inside = not inside
            continue
        mask.append(inside)
    return mask


# ── 检查 1：STD 条目的悬空引用 ────────────────────────────────

def check_std_refs(root: Path):
    defined = set()
    # 排除 PACK.md（包元信息）与 INDEX.md（演示条目格式，不是定义）。
    # INDEX.md 的示例恰好用了真实存在的编号时，错误会被"去重后计数不变"掩盖——
    # 一旦有人把示例换成别的编号，就会开始把示例当定义、并漏掉真实悬空引用。
    sources = list(root.glob("*/standards/*.md")) + [
        p for p in (root / "09_资产库" / "规范包").rglob("*.md")
        if p.name not in ("PACK.md", "INDEX.md")]
    for f in sources:
        lines = f.read_text(encoding="utf-8").split("\n")
        mask = fenced_mask(lines)
        for i, line in enumerate(lines):
            if mask[i]:
                continue
            m = re.match(r"^## (STD-[A-Z0-9-]+)", line)
            if m:
                defined.add(m.group(1))
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
    # 用 skill_md_files（已排除 projects/），与 check_mount_layer 的口径一致。
    # 早先这里直接 rglob("SKILL.md")，把项目级 Skill 也算了进来 ——
    # 于是表头打印的 Skill 数与挂载层校验的那个「Skill 全集」是两个不同的集合，
    # 数字看起来自相矛盾。项目级 Skill 由 check_project_skills 单独负责。
    names = {p.parent.name for p in skill_md_files(root)}
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
    paths = list(skill_md_files(root))
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
        # description 是 Claude skill 自动发现的前提：缺了它，这个 Skill 不会被任何会话看到
        for k in ("description", "version", "stage", "owner", "updated", "status"):
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


# ── 检查 3b：项目级 Skill ────────────────────────────────────


def check_project_skills(root: Path):
    """`projects/<码>/skills/` 下的项目级 Skill：frontmatter 与三件套。

    **与顶层 Skill 分开检查，因为规则本来就不同**：
    - **不要求** `ai-<域>-<序号>-<动作>` 命名 —— 项目级 Skill 用描述性名字
      （顶层那套命名是为了让挂载层能机械分组，项目级 Skill 不参与挂载）
    - **不要求** `stage` / `owner` 等知识库簿记字段 —— 它们不参与提升流程
    - **但 `name` / `description` / 三件套一样要求**：`description` 是 skill 发现的前提，
      三件套是"这个 Skill 能不能被照着执行"的前提

    早先这里完全是盲区：顶层检查用 `skill_md_files`（**已排除 projects/**），
    于是项目级 Skill 既不被计数也不被检查 —— 缺 `prompt.md` 也不会有人知道。
    """
    problems = []
    proj_root = root / "projects"
    if not proj_root.is_dir():
        return problems
    for proj in sorted(d for d in proj_root.iterdir()
                       if d.is_dir() and not d.name.startswith("_")):
        sk_dir = proj / "skills"
        if not sk_dir.is_dir():
            continue
        for d in sorted(x for x in sk_dir.iterdir() if x.is_dir()):
            p = d / "SKILL.md"
            rel = str(d.relative_to(root))
            if not p.is_file():
                problems.append({"kind": "project-skill",
                                 "detail": "目录里没有 SKILL.md", "where": rel})
                continue
            try:
                meta = yaml.safe_load(p.read_text(encoding="utf-8").split("---")[1]) or {}
            except Exception as e:
                problems.append({"kind": "project-skill",
                                 "detail": f"frontmatter 解析失败：{e}", "where": rel})
                continue
            if meta.get("name") != d.name:
                problems.append({"kind": "project-skill",
                                 "detail": f"name={meta.get('name')} 与目录名 {d.name} 不一致",
                                 "where": rel})
            if not meta.get("description"):
                problems.append({"kind": "project-skill",
                                 "detail": "frontmatter 缺 `description`（没有它就不会被任何会话看到）",
                                 "where": rel})
            for f in ("prompt.md", "references/INDEX.md"):
                if not (d / f).exists():
                    problems.append({"kind": "project-skill",
                                     "detail": f"缺 {f}", "where": rel})
    return problems


# ── 检查 4：上下文预算 ────────────────────────────────────────

BUDGET = {("CLAUDE.md", None): 200,
          ("SKILL.md", None): 150,
          ("prompt.md", None): 300}


def check_budget(root: Path):
    problems = []
    for f in root.rglob("*"):
        if not f.is_file() or f.name not in ("CLAUDE.md", "SKILL.md", "prompt.md"):
            continue
        parts = f.relative_to(root).parts
        if parts[0] in (".git", ".claude", "projects"):
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
    for p in skill_md_files(root):
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


def check_mount_layer(root: Path):
    """`.claude/skills/` 是给 skill 发现机制看的挂载层，由脚本生成。

    它必须与真实定义同步：description 是 Claude 决定「什么时候用哪个 skill」的依据，
    挂载层里的 description 过期，等于让模型按错误的触发条件选 Skill。
    """
    mount = root / ".claude" / "skills"
    problems = []
    names = set()
    for p in skill_md_files(root):
        try:
            meta = yaml.safe_load(p.read_text(encoding="utf-8").split("---")[1]) or {}
        except Exception:
            continue
        name, desc = meta.get("name"), meta.get("description")
        if not name:
            continue
        names.add(name)
        target = mount / name / "SKILL.md"
        if not target.is_file():
            problems.append({"kind": "mount",
                             "detail": f"`{name}` 缺少 .claude/skills/ 挂载（不会被 skill 发现机制看到）",
                             "where": str(p.relative_to(root))})
            continue
        mt = target.read_text(encoding="utf-8")
        m = re.search(r"^description: (.+)$", mt, re.M)
        if not m or m.group(1).strip() != str(desc).strip():
            problems.append({"kind": "mount",
                             "detail": f"`{name}` 挂载层的 description 与真实定义不一致",
                             "where": str(target.relative_to(root))})
    if mount.is_dir():
        for d in sorted(mount.iterdir()):
            if d.is_dir() and d.name not in names:
                problems.append({"kind": "mount",
                                 "detail": f"挂载层存在 `{d.name}`，但知识库里已无此 Skill",
                                 "where": str(d.relative_to(root))})
    return problems


# ── 检查 8：门禁检查项与清单的**双向**差集 ─────────────────────

def doc_check_ids(listing: Path) -> set[str]:
    """从检查项清单里取出声明的检查项 ID。

    **只看「检查项」表格**，即表头第一列含"检查项"的那些表。
    早期实现用 `^| `id` |` 直接匹配所有行，于是清单里任何"第一列是单个反引号词"的表格
    都会被当成检查项——比如结果语义表（`pass` / `fail` / `skip` / `external`）
    就会被读成四个"写了但没实现"的检查项，报出一片假问题。
    认表头比改文档格式可靠：文档会变，表头语义不会。
    """
    ids, in_check_table = set(), False
    lines = listing.read_text(encoding="utf-8").split("\n")
    for i, line in enumerate(lines):
        if line.lstrip().startswith("|") and i + 1 < len(lines) and is_separator(lines[i + 1]):
            head = [c.strip() for c in line.strip().strip("|").split("|")]
            in_check_table = bool(head) and "检查项" in head[0]
            continue
        if not in_check_table or not line.lstrip().startswith("|"):
            if not line.lstrip().startswith("|"):
                in_check_table = False
            continue
        m = re.match(r"^\|\s*`([a-z0-9-]+)`\s*\|", line)
        if m:
            ids.add(m.group(1))
    return ids


def check_check_registry(root: Path):
    """门禁 ↔ 执行器 ↔ 检查项清单，三者必须一一对应。

    原有实现只做单向（门禁引用了未实现的检查项）。缺了另一半会漏掉两种真实问题：
      · 实现了但没有任何门禁引用 → 死代码，没人跑它
      · 检查项清单与执行器对不上 → 清单说"查过了"，而执行器其实没查
    """
    script = root / "07_质量门禁/skills/ai-gate-runner/scripts/gate_run.py"
    listing = root / "07_质量门禁/skills/ai-gate-runner/references/检查项清单.md"
    problems = []
    if not script.is_file():
        return [{"kind": "gate", "detail": "找不到 gate_run.py", "where": "-"}]
    impl = set(re.findall(r'@check\("([a-z0-9-]+)"', script.read_text(encoding="utf-8")))

    used = set()
    gates_dir = root / "07_质量门禁/gates"
    if gates_dir.is_dir():
        for g in sorted(gates_dir.glob("gate-*.md")):
            used |= set(re.findall(r"auto:([a-z0-9-]+)", g.read_text(encoding="utf-8")))
    for c in sorted(impl - used):
        problems.append({"kind": "gate",
                         "detail": f"检查项 `{c}` 已实现但没有任何门禁引用它（死代码）",
                         "where": "gates/"})

    if listing.is_file():
        doc = doc_check_ids(listing)
        for c in sorted(impl - doc):
            problems.append({"kind": "gate",
                             "detail": f"检查项 `{c}` 有实现但没写进 检查项清单.md",
                             "where": str(listing.relative_to(root))})
        for c in sorted(doc - impl):
            problems.append({"kind": "gate",
                             "detail": f"检查项清单.md 写了 `{c}`，但执行器里没有实现",
                             "where": str(listing.relative_to(root))})
    return problems


# ── 检查 9：文档里的数字与实测是否一致 ────────────────────────

def check_counts(root: Path):
    """跨文件的数字一致性。

    README 写「团队基线 37 条」而实际 43 条——这类问题单文件检查发现不了，
    而讽刺的是：**检查器自己运行时第一行就打印了正确值**，只是没人和文档对照。
    """
    problems = []
    n_skill = len(list(skill_md_files(root)))

    base = len(set(re.findall(
        r"^## (STD-BASE-[0-9]{3})",
        "\n".join(f.read_text(encoding="utf-8") for f in root.glob("*/standards/*.md")),
        re.M)))
    pack_files = [p for p in (root / "09_资产库" / "规范包").rglob("*.md")
                  if p.name not in ("PACK.md", "INDEX.md")]
    pack = len(set(re.findall(
        r"^## (STD-[A-Z0-9-]+)",
        "\n".join(f.read_text(encoding="utf-8") for f in pack_files), re.M)))

    checks = [
        (re.compile(r"(\d+)\s*个 Skill"), n_skill, "Skill 数"),
        # 「共 N 个，全部已实现」这种写法不含 "Skill" 这个词，前一版正则漏掉了它——
        # 而它恰恰是最常用的总数表述。漏一种写法，等于这个检查时灵时不灵。
        #
        # 但它必须**只在同行出现 "Skill" 时**才算（见下面的 `_applies`）：
        # 放宽后会把「本批次共 4 个页面，覆盖全部 24 个 FN」这类句子误判成 Skill 数。
        # 误报比漏报更快地杀死一个检查器——这句话我已经在本文件里写过三次了。
        (re.compile(r"共\s*\*{0,2}(\d+)\s*个"), n_skill, "Skill 数"),
        (re.compile(r"团队基线\s*\*{0,2}(\d+)\s*条"), base, "团队基线条目数"),
        (re.compile(r"包内条目\s*\*{0,2}(\d+)\s*条"), pack, "包内条目数"),
    ]

    def _applies(pat, line: str) -> bool:
        """`共 N 个` 这条只在同句提到 Skill 时才适用，否则它匹配的是任意「共 N 个 X」。"""
        if pat.pattern.startswith("共"):
            return "Skill" in line
        return True

    # 只有"全局性文档"里的数字才是全库口径。域 README 写「本域 7 个 Skill」是对的，
    # 拿全库总数去比会得到一片误报——而误报比漏报更快地杀死一个检查器。
    GLOBAL_DOCS = ("README.md", "CLAUDE.md", "00_工作空间配置/")
    for f in md_files(root):
        rel = f.relative_to(root).as_posix()
        if not rel.startswith(GLOBAL_DOCS):
            continue
        for _, line, example in ref_lines(f):
            if example:
                continue
            for pat, actual, label in checks:
                if not _applies(pat, line):
                    continue
                for m in pat.finditer(line):
                    if int(m.group(1)) != actual:
                        problems.append({
                            "kind": "count",
                            "detail": f"{label}写作 {m.group(1)}，实测 {actual}",
                            "where": f"{rel}: {line.strip()[:70]}",
                        })
    return problems


# ── 检查 10：Markdown 结构合法性 ──────────────────────────────

def check_markdown_structure(root: Path):
    """渲染正确性和"看起来对但实际错了"的结构问题。

    以前 13 份 `standards/*.md` 全部写作 `# # 标题`——渲染时第二个 `#`
    会作为正文原样显示。没有这层检查，它就只能靠人翻文件时偶然发现。
    """
    problems = []
    for f in md_files(root, include_proposals=True):
        lines = f.read_text(encoding="utf-8").split("\n")
        mask = fenced_mask(lines)
        for i, line in enumerate(lines):
            if mask[i]:
                continue
            if re.match(r"^#{1,6}\s+#", line):
                problems.append({
                    "kind": "markdown",
                    "detail": f"畸形标题（多了一个 `#`，会原样渲染出来）：{line.strip()[:50]}",
                    "where": f"{f.relative_to(root)}:{i + 1}",
                })
            # 表格列数：表头列数必须与数据行一致，否则渲染会错位
            if (line.lstrip().startswith("|") and i + 1 < len(lines)
                    and is_separator(lines[i + 1])):
                want = table_cols(line)
                for j in range(i + 2, len(lines)):
                    row = lines[j]
                    if not row.lstrip().startswith("|") or mask[j]:
                        break
                    got = table_cols(row)
                    if got != want:
                        problems.append({
                            "kind": "markdown",
                            "detail": f"表格列数不一致（表头 {want} 列，本行 {got} 列）",
                            "where": f"{f.relative_to(root)}:{j + 1}",
                        })
    return problems


# ── 检查 11：三件套是否只是模板复制 ───────────────────────────

def check_reference_shells(root: Path):
    """多个 Skill 的 `references/INDEX.md` 逐字相同 = 模板复制，不是各自的索引。

    渐进式披露下"没有专属知识文件"本身是合法状态。但 8 份完全一样的 INDEX.md
    装在不同 Skill 目录里时，读者无法判断是"这个 Skill 真不需要"还是"这里还没写"。
    """
    import hashlib
    groups: dict[str, list[str]] = {}
    for p in skill_md_files(root):
        idx = p.parent / "references" / "INDEX.md"
        if not idx.is_file():
            continue
        txt = re.sub(r"\s+", "", idx.read_text(encoding="utf-8"))
        groups.setdefault(hashlib.sha256(txt.encode()).hexdigest(), []).append(
            str(idx.parent.parent.relative_to(root)))
    problems = []
    for members in groups.values():
        if len(members) >= 3:
            problems.append({
                "kind": "placeholder",
                "detail": (f"{len(members)} 个 Skill 的 references/INDEX.md 逐字相同"
                           f"（模板复制，未针对各自写索引）：{'、'.join(sorted(members)[:4])}…"),
                "where": "references/INDEX.md",
            })
    return problems


# ── 检查 12：扩宽的状态矛盾检测 ───────────────────────────────

# 过期表述。注意只在这些词与**被反引号包住的 Skill 名**同行时才算问题——
# 否则正文里正常讨论"未实现的检查项"会被大量误报。
STALE_PHRASES = ("未实现", "尚未实现", "待实现", "为占位", "P0 阶段唯一",
                 "随 P1", "随 P2", "（P1）", "（P2）")


def check_stale_claims(root: Path):
    """文档说某个 Skill "未实现"，而它的 `status` 是 `implemented`。

    2026-10-20 的审计发现：一次"重写状态节"的修复只落在一个文件上，
    同类表述在 12 个文件里原样存活。这类问题的复现率最高、也最难靠人发现。
    """
    implemented = set()
    for p in skill_md_files(root):
        try:
            meta = yaml.safe_load(p.read_text(encoding="utf-8").split("---")[1]) or {}
        except Exception:
            continue
        if meta.get("status") == "implemented" and meta.get("name"):
            implemented.add(meta["name"])

    problems = []
    for f in md_files(root):
        for lineno, line, example in ref_lines(f):
            if example:
                continue
            hit = [n for n in SKILL_RE.findall(line) if n in implemented]
            if not hit:
                continue
            # 一行里同时出现「已实现」时，那个「未实现」多半是条件句的一部分
            # （如「已实现——未实现时拒绝」），不是在声明它的状态。
            # 误报比漏报更快地让人不再看这份清单，所以这里宁可放宽。
            if "已实现" in line:
                continue
            if any(ph in line for ph in STALE_PHRASES):
                problems.append({
                    "kind": "status-claim",
                    "detail": (f"`{hit[0]}` 已是 implemented，本行却仍以"
                               f"「未实现 / 待交付」的口径描述它"),
                    "where": f"{f.relative_to(root)}:{lineno}: {line.strip()[:70]}",
                })
    return problems


def check_rules_drift(root: Path):
    """项目级条目的**提炼产物**与它摘录的**散文源文档**已经分叉。

    为什么这条必须进自检：`ai-spec-build` 只在**有人跑构建**时报漂移，
    而散文改了、没人跑构建、也没人看快照，是完全可能的——那时漂移没有任何一处会被说出来。
    这条检查提供一个不依赖"有人恰好跑了构建"的检测路径。

    为什么它值得单独一条：散文里新加的约束没有进快照时，
    快照看起来**一切正常**——「少一条约束」和「本来就没这条约束」在快照里长得一模一样。
    这是知识库里唯一一类"静默地少东西"的故障。
    """
    problems = []
    proj_root = root / "projects"
    if not proj_root.is_dir():
        return problems
    for proj in sorted(d for d in proj_root.iterdir() if d.is_dir() and not d.name.startswith("_")):
        rules_dir = proj / ".agent" / "rules"
        if not rules_dir.is_dir():
            continue
        for rf in sorted(rules_dir.glob("*.md")):
            try:
                text = rf.read_text(encoding="utf-8")
            except Exception as exc:
                problems.append({"kind": "rules-drift",
                                 "detail": f"rules 文件读不出来：{exc}",
                                 "where": str(rf.relative_to(root))})
                continue
            if not text.startswith("---"):
                continue          # 无 frontmatter = 手工维护文件，不是派生副本，无从比对
            fm = {}
            for raw in text.split("---", 2)[1].split("\n"):
                if ":" in raw:
                    k, v = raw.split(":", 1)
                    fm[k.strip()] = v.strip()
            src = fm.get("source", "")
            if not src:
                continue
            src_path = proj / src
            rel = f"{rf.relative_to(root)} ← {fm.get('source', '?')}"
            if not src_path.exists():
                problems.append({"kind": "rules-drift",
                                 "detail": "提炼产物的源文档不存在——条目内容无从核对",
                                 "where": rel})
                continue
            actual = "sha256:" + hashlib.sha256(
                src_path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()[:16]
            recorded = fm.get("source_hash", "")
            if recorded != actual:
                problems.append({
                    "kind": "rules-drift",
                    "detail": ("源文档已变更但条目未重新提炼——快照里的项目级约束可能缺条或过时"
                               f"（记录 {recorded or '（空）'} / 实测 {actual}）"),
                    "where": rel,
                })
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
    p7 = check_mount_layer(root)
    p8 = check_check_registry(root)
    p9 = check_counts(root)
    p10 = check_markdown_structure(root)
    p11 = check_reference_shells(root)
    p12 = check_stale_claims(root)
    p13 = check_rules_drift(root)
    p14 = check_project_skills(root)
    all_problems = (p1 + p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9 + p10 + p11 + p12
                    + p13 + p14)
    n_proj_skill = len(list((root / "projects").glob("*/skills/*/SKILL.md")))

    if args.json:
        print(json.dumps({"problems": all_problems,
                          "stats": {"std_defined": n_def, "std_referenced": n_ref,
                                    "skills": n_skill, "gate_checks": n_gate_checks,
                                    "skill_md": n_skillmd}},
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
        "mount": "Skill 挂载层不同步",
        "count": "文档数字与实测不符",
        "markdown": "Markdown 结构问题",
        "placeholder": "三件套只是模板复制",
        "rules-drift": "项目级条目与源散文已分叉",
        "project-skill": "项目级 Skill",
    }
    print(f"\n知识库一致性检查")
    print(f"  STD 条目 {n_def} 个（被引用 {n_ref} 个）｜ "
          f"顶层 Skill {n_skill} 个（挂载层）｜ 项目级 Skill {n_proj_skill} 个 ｜ "
          f"门禁检查项 {n_gate_checks} 个\n")
    if not all_problems:
        print("  ✅ 未发现跨文件不一致")
        print("     （覆盖上表各类；不含 docs/ 提案文档、不含条目正文的语义矛盾）\n")
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