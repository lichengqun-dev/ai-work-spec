#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ai-spec-build —— 项目规范底座编译器

把**项目级**规范编译成单一「项目规范底座」（下称快照），内容只有三样：

  1. 项目级条目（`.agent/rules/` 提炼产物 + manifest 内联的 `project_only`）
  2. 项目声明（本项目选了哪些包）——**指针，不是规则**
  3. 来源链与漂移告警

## 为什么快照只装项目级

域级规范（各业务域 `standards/`、`09_资产库/规范包/`）**到对应阶段按需读取原文**，
不需要编译：它们只在某个阶段用得上，读一次就够，不存在"每个阶段反复读"的问题。
只有**项目级**内容每个阶段都要用，才值得编译一次，避免反复读项目根的散文。

域级不再是本 Skill 的输入，也不参与编号校验与合并——**域级不使用条目机制**。

## 为什么仍然要在构建期做

项目级条目必须可复现、可 diff、可审计：
  1. token 成本   —— 项目根散文与 rules 每次执行都读一遍
  2. 结果确定性   —— 运行时摘要每次措辞都可能不同，规范的意义恰恰在于"每次都一样"
  3. 冲突可见性   —— 模型遇到冲突会静默挑一个；构建期遇到冲突直接失败
  4. 可审计性     —— 快照带哈希，能精确回答"这个批次当时用的是哪版规范"

用法：
  python3 spec_build.py --project <项目码>
  python3 spec_build.py --all
  python3 spec_build.py --all --check      # 只校验，不写文件
  python3 spec_build.py --list             # 列出全部包与版本

退出码：0 成功 / 1 校验失败 / 2 用法或环境错误
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("错误：缺少 PyYAML。安装：pip install pyyaml\n")
    sys.exit(2)

A_SECTION_BUDGET_LINES = 120
MAX_PROJECT_ONLY_ITEMS = 30

# 项目级条目的来源目录（相对项目目录）。
#
# 为什么是这里而不是项目根：项目根的文档是**人读的散文**——人工维护复制进来、
# 或 AI 读代码仓梳理总结出来，**不遵守编号约定**，改动频繁。
# 而快照要的是稳定的、可审计的、能追回出处的条目。两者性质不同，就不能同处一室。
RULES_DIR = ".agent/rules"

ENTRY_HEAD = re.compile(r"^##\s+(STD-[A-Z0-9-]+)\s*[·:：]\s*(.+?)\s*$")
META_BLOCK = re.compile(r"<!--\s*meta\s*(.*?)-->", re.S)
FM_BLOCK = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?", re.S)

# 快照 C 段的「什么时候去读它」——按维度给一句判据，而不是复述包名
PACK_WHEN = {
    "fe": "写前端代码、做前端设计时",
    "be": "写后端代码、做接口与分层设计时",
    "db": "写 SQL、建表改表、做数据库设计时",
}


class BuildError(Exception):
    """校验失败：构建必须中止。"""


@dataclass
class Entry:
    """项目级条目。域级条目不进本结构——它们在阶段里按原文读。"""
    id: str
    title: str
    source: str
    origin_file: str
    body: str = ""
    tier: str = "indexed"        # resident | indexed
    scope: str = ""
    status: str = "active"       # active（保留字段，便于将来支持条目废弃）
    note: str = ""

    def rule_line(self) -> str:
        """取条目正文中 **规则** 那一句，用于快照 A 段摘要。"""
        m = re.search(r"\*\*规则\*\*[：:]\s*(.+?)(?:\n\n|\Z)", self.body, re.S)
        text = m.group(1) if m else (self.body.strip().split("\n\n")[0] if self.body.strip() else "")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:110] + ("…" if len(text) > 110 else "")


@dataclass
class Pack:
    """规范包。本编译器只用它的**声明**（选了哪些包、版本、状态），不读包内条目。"""
    pack_id: str
    key: str
    dimension: str
    version: str
    title: str
    prefix: str
    status: str
    path: Path


# ── 基础工具 ────────────────────────────────────────────────

def find_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "CLAUDE.md").is_file() and (p / "09_资产库").is_dir():
            return p
    raise BuildError("未找到仓库根目录（需同时存在 CLAUDE.md 与 09_资产库/）")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha256_of(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def md_cell(s) -> str:
    """把一段文本安全地放进 Markdown 表格单元格。

    必须处理两样东西：

    · **`|`** —— 单元格分隔符。条目标题里出现竖线是**正常情况**（写 SQL 的 `||` 拼接运算符、
      写 `a | b` 的取值枚举），但不转义就会把表格切错列。而快照是给人读的索引，
      列一错位整段就不可信，且**不报任何错**。
    · **换行** —— 会在表格中间断开，后续行变成表格外的正文。

    这个 bug 是真实发生过的：某个包的条目标题里写了 `||`，导致快照的 B 段索引表多出两列。
    事后靠一致性检查的 Markdown 结构校验才发现。
    """
    return str(s).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").strip()


def parse_frontmatter(text: str):
    """解析 Markdown 的 YAML frontmatter，返回 (meta, body)。"""
    m = FM_BLOCK.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as exc:
        raise BuildError(f"frontmatter YAML 解析失败：{exc}")
    if not isinstance(meta, dict):
        raise BuildError("frontmatter 必须是 YAML 映射")
    return meta, text[m.end():]


def split_fences(lines: list[str]) -> list[bool]:
    """标记每一行是否处于代码围栏内部，避免把围栏里的 ## 当成条目头。"""
    inside, flags = False, []
    for line in lines:
        flags.append(inside)
        if line.lstrip().startswith("```"):
            inside = not inside
    return flags


# ── 条目解析（只用于项目级 rules）────────────────────────────

def parse_entries(text: str, project: str, origin_file: str) -> list[Entry]:
    """解析 `## STD-PRJ-…` 条目。

    **只对项目级提炼产物调用。** 域级规范文件里的 `## STD-…` 标题现在是**段落锚点**
    （供人引用与定位），不再被解析成条目——域级不使用条目机制。
    """
    lines = text.split("\n")
    fenced = split_fences(lines)

    heads: list[tuple[int, str, str]] = []
    for i, line in enumerate(lines):
        if fenced[i]:
            continue
        m = ENTRY_HEAD.match(line)
        if m:
            heads.append((i, m.group(1), m.group(2)))

    entries: list[Entry] = []
    for n, (idx, entry_id, title) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        body = "\n".join(lines[idx + 1:end]).strip()

        meta: dict = {}
        mm = META_BLOCK.search(body)
        if mm:
            for raw in mm.group(1).split("\n"):
                raw = raw.strip().lstrip("*").strip()
                if not raw or ":" not in raw:
                    continue
                k, v = raw.split(":", 1)
                meta[k.strip()] = v.strip()
            body = (body[:mm.start()] + body[mm.end():]).strip()

        entries.append(Entry(
            id=entry_id,
            title=title,
            source=project,
            origin_file=origin_file,
            body=body,
            tier=str(meta.get("tier", "indexed")).strip().lower(),
            scope=str(meta.get("scope", "")).strip(),
        ))
    return entries


# ── 包声明加载 ──────────────────────────────────────────────

def load_pack(pack_dir: Path, dimension: str) -> Pack:
    """只读 `PACK.md` 的声明，**不读包内条目文件的内容**。

    `files` 列出的文件仍要存在（校验项 1）——它们是阶段加载时要去读的原文，
    路径写错了会让人在对应阶段找不到规范，而那时已经离错误现场很远。
    """
    pack_md = pack_dir / "PACK.md"
    if not pack_md.is_file():
        raise BuildError(f"包缺少 PACK.md：{pack_dir}")

    meta, _ = parse_frontmatter(read_text(pack_md))
    for req in ("pack", "key", "version", "files"):
        if req not in meta:
            raise BuildError(f"{pack_md} 的 frontmatter 缺少必填字段 `{req}`")
    if not isinstance(meta.get("files"), list):
        raise BuildError(f"{pack_md} 的 `files` 必须是列表（可为空列表）")

    for fname in meta["files"]:
        fpath = pack_dir / fname
        if not fpath.is_file():
            raise BuildError(f"{pack_md} 中列出的条目文件不存在：{fpath}")

    return Pack(
        pack_id=str(meta["pack"]),
        key=str(meta["key"]),
        dimension=dimension,
        version=str(meta["version"]),
        title=str(meta.get("title", meta["pack"])),
        prefix=str(meta.get("prefix", "")),
        status=str(meta.get("status", "unknown")),
        path=pack_dir,
    )


def discover_packs(root: Path) -> dict[str, Pack]:
    """扫描 09_资产库/规范包/{stacks,domains}/ 下的全部包。"""
    packs: dict[str, Pack] = {}
    base = root / "09_资产库" / "规范包"
    for dimension, sub in (("stack", "stacks"), ("domain", "domains")):
        d = base / sub
        if not d.is_dir():
            continue
        for pack_dir in sorted(p for p in d.iterdir() if p.is_dir()):
            pack = load_pack(pack_dir, dimension)
            if pack.pack_id in packs:
                raise BuildError(f"包 id 重复：{pack.pack_id}（{pack_dir}）")
            packs[pack.pack_id] = pack
    return packs


# ── manifest ────────────────────────────────────────────────

def load_manifest(root: Path, project: str) -> dict:
    path = root / "projects" / project / ".agent" / "project.yaml"
    if not path.is_file():
        raise BuildError(f"找不到项目 manifest：{path}")
    try:
        data = yaml.safe_load(read_text(path)) or {}
    except yaml.YAMLError as exc:
        raise BuildError(f"{path} YAML 解析失败：{exc}")
    if not isinstance(data, dict):
        raise BuildError(f"{path} 必须是 YAML 映射")
    if data.get("project") != project:
        raise BuildError(f"{path} 中 project={data.get('project')!r} 与目录名 {project!r} 不一致")
    return data


def parse_pin(value: str, where: str) -> tuple[str, str]:
    if "@" not in str(value):
        raise BuildError(f"{where} 必须是 `<包名>@<版本>` 形式，收到 {value!r}")
    name, version = str(value).rsplit("@", 1)
    return name.strip(), version.strip()


def resolve_packs(manifest: dict, packs: dict[str, Pack], project: str):
    """按 manifest 选出技术栈包与领域包（领域包保持声明顺序=优先级）。

    校验项 2：包必须存在，且**版本必须与 manifest 锁定的一致**——
    包升级不会自动影响项目，升级要显式改 manifest。
    """
    stacks, domains = [], []
    for key, value in (manifest.get("stacks") or {}).items():
        for item in (value if isinstance(value, list) else [value]):
            name, version = parse_pin(item, f"{project}.stacks.{key}")
            pack = packs.get(name)
            if pack is None:
                raise BuildError(f"manifest 引用了不存在的技术栈包：{name}")
            if pack.version != version:
                raise BuildError(
                    f"技术栈包版本不匹配：manifest 锁定 {name}@{version}，"
                    f"包实际为 @{pack.version}（升级请改 manifest，不要改包）"
                )
            if pack.key != key:
                raise BuildError(f"包 {name} 的 key={pack.key}，与 manifest 中使用的键 {key} 不一致")
            stacks.append((key, name, version))
    for item in (manifest.get("domains") or []):
        name, version = parse_pin(item, f"{project}.domains")
        pack = packs.get(name)
        if pack is None:
            raise BuildError(f"manifest 引用了不存在的领域包：{name}")
        if pack.version != version:
            raise BuildError(
                f"领域包版本不匹配：manifest 锁定 {name}@{version}，包实际为 @{pack.version}"
            )
        domains.append((name, version))
    return stacks, domains


# ── 项目级条目 ──────────────────────────────────────────────

def load_rules_files(root: Path, project: str) -> list[tuple[Path, dict, str]]:
    """读取 `<项目>/.agent/rules/*.md`，返回 [(路径, frontmatter, 正文)]。

    目录不存在时返回空列表——项目可以合理地没有项目级条目，这不是错误。
    """
    d = root / "projects" / project / RULES_DIR
    if not d.is_dir():
        return []
    out: list[tuple[Path, dict, str]] = []
    for md in sorted(d.glob("*.md")):
        fm, body = parse_frontmatter(read_text(md))
        out.append((md, fm, body))
    return out


def check_rules_drift(root: Path, project: str,
                      rules: list[tuple[Path, dict, str]]) -> list[dict]:
    """比对 rules 文件记录的源文档哈希与源文档当前哈希。

    **这是这套机制能成立的关键。** 提炼产物是散文的**派生副本**，散文可以随便改，
    改了而没重新提炼，快照就会悄悄停留在旧规则上——而且不报错，因为「少了一条约束」
    和「本来就没有这条约束」在快照里长得一模一样。

    所以每条 rules 文件都记着「我提炼自哪个文件、当时它的哈希是多少」，构建时比对。
    不一致不判失败（改文档是常态，判失败会逼人在改错别字时也重跑提炼），
    但要**同时**写进 stderr 与快照正文——快照是 AI 运行时唯一会读的东西，
    告警只打在 stderr 上等于没有告警。
    """
    proj_dir = root / "projects" / project
    drift: list[dict] = []
    for md, fm, _body in rules:
        src = str(fm.get("source") or "").strip()
        if not src:
            # 没有 source 的 rules 文件是**手工维护**的，不是派生副本，无从比对。
            continue
        recorded = str(fm.get("source_hash") or "").strip()
        src_path = proj_dir / src
        item = {"rules_file": f"{RULES_DIR}/{md.name}", "source": src, "recorded": recorded}
        if not src_path.exists():
            item["kind"] = "missing"
            item["actual"] = None
            item["note"] = f"源文档不存在：projects/{project}/{src}"
            drift.append(item)
            continue
        actual = sha256_of(read_text(src_path))
        if recorded != actual:
            item["kind"] = "changed"
            item["actual"] = actual
            item["note"] = ""
            drift.append(item)
    return drift


def load_project_entries(root: Path, project: str, manifest: dict):
    """项目级条目，两个来源，都归项目层：

    1. `manifest` 的 `project_only` —— 极少量、不值得单独成文的条目，直接内联在组合声明里
    2. `<项目>/.agent/rules/*.md` —— **主力路径**，由 `ai-spec-extract` 从项目根散文提炼

    第 2 条为什么不直接扫项目根的 `.md`：项目根的文档是**人读的散文**，
    人工维护复制进来或 AI 梳理代码仓产出，**不遵守编号约定**且改动频繁。
    要求散文里带 `## STD-PRJ-` 编号头，等于把机器格式硬塞进人写的东西里——
    要么人烦到不写，要么格式偷偷漂掉而构建安静地少算几条。
    分成两层：散文怎么改都行，提炼产物才是机器读的那一层，且有哈希可追溯。

    校验项 3 / 4：项目级条目前缀必须正确，编号必须唯一。
    """
    added: list[Entry] = []
    prefix = f"STD-PRJ-{project.upper()}-"

    for item in (manifest.get("project_only") or []):
        if not isinstance(item, dict) or "id" not in item:
            raise BuildError("project_only 的每一项必须是含 `id` 的映射")
        eid = str(item["id"])
        if not eid.startswith(prefix):
            raise BuildError(f"项目级条目 {eid} 的前缀必须是 {prefix}")
        body_parts = [str(item.get("content", "")).strip()]
        ex = item.get("examples") or {}
        if ex:
            body_parts.append(f"**正例**：{ex.get('good', '')}\n\n**反例**：{ex.get('bad', '')}")
        added.append(Entry(
            id=eid, title=str(item.get("category", "项目级条目")),
            source=project, origin_file=".agent/project.yaml",
            body="\n\n".join(p for p in body_parts if p),
            tier=str(item.get("tier", "indexed")), scope=str(item.get("scope", "项目约束")),
        ))

    rules = load_rules_files(root, project)
    drift = check_rules_drift(root, project, rules)

    for md, _fm, body in rules:
        parsed = parse_entries(body, project, f"{RULES_DIR}/{md.name}")
        for entry in parsed:
            if not entry.id.startswith(prefix):
                raise BuildError(
                    f"项目级条目前缀不符：{entry.id}（见 projects/{project}/{RULES_DIR}/{md.name}）\n"
                    f"  本项目条目的编号前缀必须是 {prefix}\n"
                    f"  若这是格式示例，把编号写成占位形式（如 {prefix}<序号>），"
                    f"它就不会被当成真实条目解析。"
                )
        added += parsed

    by_id: dict[str, Entry] = {}
    for entry in added:
        if entry.id in by_id:
            first = by_id[entry.id]
            raise BuildError(
                f"项目级条目编号重复：{entry.id}\n"
                f"  首次出现：{first.origin_file}\n"
                f"  再次出现：{entry.origin_file}\n"
                f"  编号一经启用不复用（见 命名与编号规范.md 第 5 节）"
            )
        by_id[entry.id] = entry
    return list(by_id.values()), drift, rules


def stray_project_entries(root: Path, project: str) -> list[str]:
    """扫项目根的 `.md`，找出**看起来像条目头但不会被解析**的地方。

    只在项目根做，不递归（`<需求名>/` 下是业务级产出物）。
    用途：给人一句明确的迁移提示，而不是让「写了编号却没用」静默发生。
    """
    proj_dir = root / "projects" / project
    if not proj_dir.is_dir():
        return []
    hits: list[str] = []
    for md in sorted(proj_dir.glob("*.md")):
        for i, line in enumerate(read_text(md).split("\n"), 1):
            if ENTRY_HEAD.match(line):
                hits.append(f"projects/{project}/{md.name}:{i}  {line.strip()}")
    return hits


# ── 输出 ────────────────────────────────────────────────────

def manifest_fingerprint(manifest: dict) -> str:
    """从 manifest 里提取**与规范有关**的部分，算一个指纹。

    **不能用整个文件的哈希。** 那会把与规范无关的东西一起算进去：仓库路径、模块码、
    负责人、注释、空行。实测过一次：只在 manifest 里加了一行 `prototype_repo`
    （一个仓库路径，不是规范），快照哈希就从 `27a602e2…` 变成 `873ad184…`，
    而生效的规范**一条都没变**。

    后果很具体：批次状态文件记录的 `spec_snapshot.hash` 会无缘无故对不上，
    让人以为"规范被人改了"——而回答"这个批次当时用的是哪版规范"恰恰是这个哈希存在的唯一理由。
    一个会因无关改动而报警的哈希，等于不会报警。

    只取三样：**选了什么包（stacks/domains）、有哪些项目级条目（project_only）**。
    提炼产物的内容另有 `entries` 参与哈希，两者互补。
    """
    def _norm(v):
        if isinstance(v, list):
            return [_norm(x) for x in v]
        if isinstance(v, dict):
            return {k: _norm(v[k]) for k in sorted(v)}
        return v

    payload = {
        "stacks": _norm(manifest.get("stacks") or {}),
        "domains": _norm(manifest.get("domains") or []),
        "project_only": _norm([(o or {}).get("id")
                               for o in (manifest.get("project_only") or [])]),
    }
    return sha256_of(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def compute_snapshot_hash(manifest_fp: str, entries: list[Entry]) -> str:
    """快照哈希 —— 内容寻址，不是文件字节哈希。

    由「manifest 指纹（只含规范相关字段）+ 每条目的 id/正文哈希」算出，
    因此和输出格式无关：调整段落版式不会让它变，改一条条目就会让它变，
    **而与规范无关的改动（仓库路径、模块码、注释）也不会让它变**。
    这正是「这个批次用的是哪版规范」需要的性质。
    """
    parts = [manifest_fp]
    for e in sorted(entries, key=lambda x: x.id):
        parts.append(f"{e.id}|{e.tier}|{sha256_of(e.body)}")
    return sha256_of("\n".join(parts))


def build_snapshot_md(project: str, manifest: dict, packs, stacks, domains,
                      entries: list[Entry], drift: list[dict],
                      rules_index: list[dict]) -> str:
    resident = sorted((e for e in entries if e.tier == "resident"), key=lambda x: x.id)
    indexed = sorted((e for e in entries if e.tier != "resident"), key=lambda x: x.id)

    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %z")
    out: list[str] = []
    out.append(f"# 项目规范底座 · {project}\n")
    out.append(f"> 生成时间：{now}　｜　组合声明指纹：{manifest_fingerprint(manifest)}")
    out.append(f"> 快照哈希：{compute_snapshot_hash(manifest_fingerprint(manifest), entries)}"
               f"　（批次状态文件 `spec_snapshot.hash` 填这个值）")
    out.append("> **本文件由 ai-spec-build 生成，请勿手工编辑**——下次构建会覆盖。\n")

    out.append("> ## ⚠️ 本快照只装项目级内容")
    out.append(">")
    out.append("> 团队基线（各域 `standards/`）与技术栈包（`09_资产库/规范包/`）的规范"
               "**不在本文件里**。")
    out.append("> 它们是**域级内容**，到对应阶段按各域 `README.md` 的「本阶段约束」表读取原文。")
    out.append(">")
    out.append("> 理由：域级规范随阶段按需加载就够；只有**项目级**内容需要在这里编译一次，")
    out.append("> 避免每个阶段都把项目根的散文重读一遍。")
    out.append("> **C 段列出了本项目声明了哪些包——那是去读包原文的指针。**\n")
    out.append(f"本项目级条目 **{len(entries)}** 条（常驻 {len(resident)} / 按需 {len(indexed)}）。\n")

    # 漂移告警必须写在**快照正文**里，不能只打 stderr：
    # 快照是 AI 运行时唯一会读的东西，而「少了一条约束」与「本来就没这条」在快照里长得一样，
    # 只有这行告警能把两者区分开。
    if drift:
        out.append("> ## ⚠️ 项目级条目可能已过期")
        out.append(">")
        out.append("> 下列提炼文件的**源文档已变更**，条目尚未重新提炼。"
                   "当前快照里的项目级约束可能缺条或过时——**不要假定它完整**。\n>")
        out.append("> | 提炼文件 | 源文档 | 情况 |")
        out.append("> |---|---|---|")
        for d in drift:
            why = "源文档已变更" if d["kind"] == "changed" else "源文档不存在"
            out.append(f"> | `{md_cell(d['rules_file'])}` | `{md_cell(d['source'])}` | {why} |")
        out.append(">")
        out.append("> 处理：调用 `ai-spec-extract` 重新提炼，然后重跑本构建。\n")

    out.append("## A. 项目级常驻注入\n")
    out.append(f"_（{len(resident)} 条，预算 ≤{A_SECTION_BUDGET_LINES} 行。本项目独有的、"
               "**不看就会做错**的规则；应注入批次 `CLAUDE.md` 常驻。）_\n")
    if not resident:
        out.append("_（无）_\n")
    for e in resident:
        out.append(f"- **[{e.id}]** {e.title}")
        line = e.rule_line()
        if line:
            out.append(f"  - {line}")
    out.append("")

    out.append("## B. 项目级按需索引\n")
    out.append("_（其余项目级条目。执行到具体任务时按「触发场景」读取条目原文，不要全量读。）_\n")
    out.append("| 条目 ID | 摘要 | 来源 | 触发场景 |")
    out.append("|---|---|---|---|")
    for e in indexed:
        out.append(f"| `{e.id}` | {md_cell(e.title)} | {md_cell(e.origin_file)} | "
                   f"{md_cell(e.scope or '—')} |")
    out.append("")

    out.append("## C. 项目声明：本项目选了哪些包\n")
    out.append("_（**这一段的用途是「指路」，不是「给规则」**——快照不含包内条目，"
               "按上表到对应阶段去读包原文。）_\n")
    out.append("| 维度 | 包 | 版本 | 包状态 | 什么时候去读它 |")
    out.append("|---|---|---|---|---|")
    for key, name, version in stacks:
        out.append(f"| `{key}` | {md_cell(name)} | {version} | {packs[name].status} | "
                   f"{md_cell(PACK_WHEN.get(key, '用到该技术栈时'))} |")
    for name, version in domains:
        out.append(f"| `domain` | {md_cell(name)} | {version} | {packs[name].status} | "
                   f"涉及该领域决策时 |")
    out.append("")
    out.append(f"- 领域包优先级（高 → 低）：{' > '.join(n for n, _ in domains) or '（无）'}")
    out.append("- 包原文位置：知识库根下 `09_资产库/规范包/stacks/<包>/` 与 `.../domains/<包>/`\n")

    out.append("## D. 项目级条目的来源\n")
    if not rules_index and not entries:
        out.append("_（本项目没有项目级条目。）_\n")
    elif not rules_index:
        out.append("_（项目级条目全部来自 manifest 的内联 `project_only`，无提炼文件。）_\n")
    else:
        drift_by_file = {d["rules_file"]: d for d in drift}
        out.append("| 提炼文件 | 条目数 | 源文档 | 来源状态 |")
        out.append("|---|---|---|---|")
        for r in rules_index:
            d = drift_by_file.get(r["rules_file"])
            if d is None:
                status = "✅ 与源文档一致" if r["source"] else "手工维护（无源文档）"
            elif d["kind"] == "changed":
                status = "⚠️ 源文档已变更，待重新提炼"
            else:
                status = "❌ 源文档不存在"
            out.append(f"| `{r['rules_file']}` | {r['count']} | "
                       f"{'`' + md_cell(r['source']) + '`' if r['source'] else '—'} | {status} |")
        out.append("")
        out.append("_（提炼产物是散文的派生副本，`source_hash` 是它的「保质期」——"
                   "散文改了而没重新提炼，上表会报「已变更」。）_\n")
    return "\n".join(out)


def build_snapshot_json(project, manifest, packs, stacks, domains, entries,
                        drift: list[dict], rules_index: list[dict]) -> str:
    doc = {
        "project": project,
        "scope": "project-only",
        "manifest_hash": manifest_fingerprint(manifest),
        "snapshot_hash": compute_snapshot_hash(manifest_fingerprint(manifest), entries),
        "built_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "packs": ([{"dimension": "stack", "key": k, "pack": n, "version": v,
                    "status": packs[n].status} for k, n, v in stacks]
                  + [{"dimension": "domain", "pack": n, "version": v,
                      "status": packs[n].status} for n, v in domains]),
        "domain_priority": [n for n, _ in domains],
        # 漂移**不进** snapshot_hash：hash 是「规范内容的指纹」，
        # 而漂移是「派生副本可能过期」的状态——两者混在一处，
        # 「这个批次用的是哪版规范」就会被一个与规范内容无关的字段搅浑。
        "rules_drift": drift,
        "rules_index": rules_index,
        "entries": [
            {"id": e.id, "title": e.title, "source": e.source,
             "origin_file": e.origin_file, "tier": e.tier, "scope": e.scope,
             "status": e.status, "note": e.note}
            for e in sorted(entries, key=lambda x: x.id)
        ],
    }
    return json.dumps(doc, ensure_ascii=False, indent=2)


# ── 主流程 ──────────────────────────────────────────────────

def build_one(root: Path, packs: dict, project: str, check_only: bool, verbose: bool) -> int:
    manifest = load_manifest(root, project)
    stacks, domains = resolve_packs(manifest, packs, project)
    entries, drift, rules = load_project_entries(root, project, manifest)

    # 每个 rules 文件的条目数与来源，用于快照的 D 段来源表
    per_file: dict[str, int] = {}
    for e in entries:
        per_file[e.origin_file] = per_file.get(e.origin_file, 0) + 1
    rules_index = [{
        "rules_file": f"{RULES_DIR}/{md.name}",
        "source": str(fm.get("source") or "").strip(),
        "source_hash": str(fm.get("source_hash") or "").strip(),
        "count": per_file.get(f"{RULES_DIR}/{md.name}", 0),
    } for md, fm, _body in rules]

    md = build_snapshot_md(project, manifest, packs, stacks, domains, entries, drift, rules_index)
    js = build_snapshot_json(project, manifest, packs, stacks, domains, entries, drift, rules_index)

    # A 段预算检查
    a_lines, in_a = 0, False
    for line in md.split("\n"):
        if line.startswith("## A."):
            in_a = True
        elif line.startswith("## B."):
            in_a = False
        elif in_a:
            a_lines += 1
    if a_lines > A_SECTION_BUDGET_LINES:
        sys.stderr.write(
            f"⚠️  {project}：常驻注入段 {a_lines} 行，超过 {A_SECTION_BUDGET_LINES} 行预算。\n"
            f"    说明有非硬约束的条目被打成了 tier: resident —— 判据是「不看这条会不会做错」。\n"
        )
    if drift:
        sys.stderr.write(
            f"⚠️  {project}：{len(drift)} 个提炼文件的源文档已变更，项目级条目可能已过期。\n"
            f"    调用 ai-spec-extract 重新提炼后重跑本构建。\n"
        )
        for d in drift:
            sys.stderr.write(f"      · {d['rules_file']} ← {d['source']}（{d['kind']}）\n")
        sys.stderr.write("    注意：构建**不会**因此失败，快照照常产出——"
                         "但快照正文顶部已标注该告警。\n")

    stray = stray_project_entries(root, project)

    if not check_only:
        # 快照与日志都落在**项目目录**下（projects/<项目码>/.agent/）——它们是项目数据：
        # 内容带该项目的规范组合结果，且可由 manifest + 提炼产物重建。
        # 放在顶层会让多个项目的快照混在一处，也让"00~09 是通用资产"这条红线自相矛盾。
        proj_ai = root / "projects" / project / ".agent"
        out_dir = proj_ai / "spec-effective"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{project}.md").write_text(md, encoding="utf-8")
        (out_dir / f"{project}.json").write_text(js, encoding="utf-8")
        log = {
            "at": datetime.now(timezone.utc).astimezone().isoformat(),
            "project": project,
            "entries": len(entries),
            "manifest_hash": manifest_fingerprint(manifest),
            "snapshot_hash": compute_snapshot_hash(manifest_fingerprint(manifest), entries),
        }
        logs = proj_ai / "logs" / "spec-build.jsonl"
        logs.parent.mkdir(parents=True, exist_ok=True)
        with logs.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(log, ensure_ascii=False) + "\n")

    resident = sum(1 for e in entries if e.tier == "resident")
    print(f"✅ {project}：项目级条目 {len(entries)} 条（常驻 {resident}）"
          f"{'  [--check，未写文件]' if check_only else ''}")
    if stray:
        sys.stderr.write(
            f"⚠️  {project}：项目根的文档里有 {len(stray)} 处形如条目头的行，但**不会被解析**。\n"
            f"    项目级条目只从 {RULES_DIR}/ 读——那是机器面，项目根是给人的散文。\n"
            f"    处理：调用 ai-spec-extract 把约束提炼进 rules，然后把散文里那行改成普通的标题或段落。\n"
        )
        for s in stray:
            sys.stderr.write(f"      · {s}\n")
    if verbose:
        for key, name, version in stacks:
            print(f"     stack  {key:<4} {name}@{version} ({packs[name].status})")
        for name, version in domains:
            print(f"     domain      {name}@{version} ({packs[name].status})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="ai-spec-build · 项目规范底座编译器")
    ap.add_argument("--project", help="项目码（projects/ 下的目录名）")
    ap.add_argument("--all", action="store_true", help="编译 projects/ 下全部项目")
    ap.add_argument("--check", action="store_true", help="只校验，不写文件")
    ap.add_argument("--list", action="store_true", help="列出全部规范包")
    ap.add_argument("--repo", help="仓库根目录（默认自动向上查找）")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    try:
        root = Path(args.repo).resolve() if args.repo else find_root(Path(__file__).resolve())
        packs = discover_packs(root)

        if args.list:
            for layer, sub in (("技术栈包", "stack"), ("领域包", "domain")):
                print(f"\n【{layer}】")
                for p in sorted((v for v in packs.values() if v.dimension == sub),
                                key=lambda x: x.pack_id):
                    print(f"  {p.pack_id:<26} @{p.version:<8} {p.status:<9} {p.title}")
            print("\n（包内条目不进快照——到对应阶段按包原文读。"
                  "条目本身在 `PACK.md` 的 `files` 列出的文件里。）\n")
            return 0

        if args.all:
            projects = sorted(d.name for d in (root / "projects").iterdir()
                              if d.is_dir() and not d.name.startswith("_"))
            if not projects:
                print("未发现可编译的项目。\n")
                print("本仓库是通用资产，projects/ 下默认只有 _template/（模板不参与构建）。")
                print("接入第一个项目：\n")
                print("  cp -r projects/_template projects/<项目码>")
                print("  # 填 projects/<项目码>/.agent/project.yaml（选包 + 差异）")
                print("  python3 00_工作空间配置/skills/ai-spec-build/scripts/spec_build.py "
                      "--project <项目码>\n")
                print("查看可选规范包：加 --list\n")
                return 0
        elif args.project:
            projects = [args.project]
        else:
            ap.error("需要 --project <项目码> 或 --all（或 --list）")

        failed = 0
        for project in projects:
            try:
                build_one(root, packs, project, args.check, args.verbose)
            except BuildError as exc:
                failed += 1
                sys.stderr.write(f"\n❌ {project} 构建失败：\n{exc}\n")
        if failed:
            sys.stderr.write(f"\n共 {failed} 个项目构建失败。\n")
            return 1
        return 0
    except BuildError as exc:
        sys.stderr.write(f"\n❌ {exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())