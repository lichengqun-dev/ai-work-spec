#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ai-spec-build —— 规范编译器

把多层规范（团队基线 / 技术栈包 / 领域包 / 项目层 / 批次特例）编译成单一「生效规范快照」。

为什么必须在构建期合并，而不是让模型运行时读多层文件自己合并：
  1. token 成本   —— 五层全文每次执行都要读一遍
  2. 结果确定性   —— 运行时合并每次结果可能不同，规范的意义恰恰在于"每次都一样"
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

# ── 层级定义 ────────────────────────────────────────────────
LAYER_RANK = {"baseline": 0, "stack": 10, "domain": 20, "project": 30, "batch": 40}
LAYER_LABEL = {
    "baseline": "L0 团队基线",
    "stack": "L1 技术栈包",
    "domain": "L2 领域包",
    "project": "L3 项目层",
    "batch": "L4 批次特例",
}

A_SECTION_BUDGET_LINES = 120
MAX_PROJECT_ONLY_ITEMS = 30

ENTRY_HEAD = re.compile(r"^##\s+(STD-[A-Z0-9-]+)\s*[·:：]\s*(.+?)\s*$")
META_BLOCK = re.compile(r"<!--\s*meta\s*(.*?)-->", re.S)
FM_BLOCK = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?", re.S)
DEFAULT_MAX_PAGE = 3


class BuildError(Exception):
    """校验失败：构建必须中止。"""


@dataclass
class Entry:
    id: str
    title: str
    layer: str
    source: str
    origin_file: str
    body: str = ""
    tier: str = "indexed"
    scope: str = ""
    frozen: bool = False
    conflicts_with: list[str] = field(default_factory=list)
    status: str = "active"          # active | overridden | disabled | shadowed
    note: str = ""                  # 裁决说明，写进快照 C 段

    def rule_line(self) -> str:
        """取条目正文中 **规则** 那一句，用于快照 A 段摘要。"""
        m = re.search(r"\*\*规则\*\*[：:]\s*(.+?)(?:\n\n|\Z)", self.body, re.S)
        text = m.group(1) if m else (self.body.strip().split("\n\n")[0] if self.body.strip() else "")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:110] + ("…" if len(text) > 110 else "")


@dataclass
class Pack:
    pack_id: str
    key: str
    dimension: str
    version: str
    title: str
    prefix: str
    status: str
    path: Path
    entries: list[Entry] = field(default_factory=list)


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


# ── 条目解析 ────────────────────────────────────────────────

def parse_entries(text: str, layer: str, source: str, origin_file: str) -> list[Entry]:
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

        conflicts = [s.strip() for s in str(meta.get("conflicts_with", "")).split(",") if s.strip()]
        entries.append(Entry(
            id=entry_id,
            title=title,
            layer=layer,
            source=source,
            origin_file=origin_file,
            body=body,
            tier=str(meta.get("tier", "indexed")).strip().lower(),
            scope=str(meta.get("scope", "")).strip(),
            frozen=str(meta.get("frozen", "false")).strip().lower() == "true",
            conflicts_with=conflicts,
        ))
    return entries


# ── 包加载 ──────────────────────────────────────────────────

def load_pack(pack_dir: Path, dimension: str) -> Pack:
    pack_md = pack_dir / "PACK.md"
    if not pack_md.is_file():
        raise BuildError(f"包缺少 PACK.md：{pack_dir}")

    meta, _ = parse_frontmatter(read_text(pack_md))
    for req in ("pack", "key", "version", "files"):
        if req not in meta:
            raise BuildError(f"{pack_md} 的 frontmatter 缺少必填字段 `{req}`")
    if not isinstance(meta.get("files"), list):
        raise BuildError(f"{pack_md} 的 `files` 必须是列表（可为空列表）")

    entries: list[Entry] = []
    for fname in meta["files"]:
        fpath = pack_dir / fname
        if not fpath.is_file():
            raise BuildError(f"{pack_md} 中列出的条目文件不存在：{fpath}")
        entries += parse_entries(read_text(fpath), dimension, str(meta["pack"]), fname)

    return Pack(
        pack_id=str(meta["pack"]),
        key=str(meta["key"]),
        dimension=dimension,
        version=str(meta["version"]),
        title=str(meta.get("title", meta["pack"])),
        prefix=str(meta.get("prefix", "")),
        status=str(meta.get("status", "unknown")),
        path=pack_dir,
        entries=entries,
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


def load_baseline(root: Path) -> list[Entry]:
    """L0 基线 = 各业务域 standards/ 下的全部条目文件。"""
    entries: list[Entry] = []
    for domain in sorted(root.iterdir()):
        if not domain.is_dir() or not re.match(r"^\d{2}_", domain.name):
            continue
        std = domain / "standards"
        if not std.is_dir():
            continue
        for md in sorted(std.rglob("*.md")):
            rel = f"{domain.name}/standards/{md.relative_to(std)}"
            entries += parse_entries(read_text(md), "baseline", "baseline", rel)
    return entries


# ── manifest ────────────────────────────────────────────────

def load_manifest(root: Path, project: str) -> dict:
    path = root / "projects" / project / "project.yaml"
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
    """按 manifest 选出技术栈包与领域包（领域包保持声明顺序=优先级）。"""
    stacks, domains = [], []
    for key, value in (manifest.get("stacks") or {}).items():
        for item in (value if isinstance(value, list) else [value]):
            name, version = parse_pin(item, f"{project}.stacks.{key}")
            stacks.append((key, name, version))
    for item in (manifest.get("domains") or []):
        name, version = parse_pin(item, f"{project}.domains")
        domains.append((name, version))
    return stacks, domains


# ── 合并 ────────────────────────────────────────────────────

def merge(packs, stacks, domains, baseline_entries):
    """按层级装配条目，返回 (entries_by_id, 顺序列表)。"""
    ordered: list[Entry] = []
    ordered += baseline_entries

    domain_priority = {name: i for i, (name, _) in enumerate(domains)}
    for key, name, version in stacks:
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
        ordered += pack.entries

    for name, version in domains:
        pack = packs.get(name)
        if pack is None:
            raise BuildError(f"manifest 引用了不存在的领域包：{name}")
        if pack.version != version:
            raise BuildError(
                f"领域包版本不匹配：manifest 锁定 {name}@{version}，包实际为 @{pack.version}"
            )
        ordered += pack.entries

    by_id: dict[str, Entry] = {}
    for entry in ordered:
        if entry.id in by_id:
            first = by_id[entry.id]
            raise BuildError(
                f"条目编号冲突：{entry.id}\n"
                f"  首次出现：{first.source} / {first.origin_file}\n"
                f"  再次出现：{entry.source} / {entry.origin_file}\n"
                f"  编号必须全库唯一（见 命名与编号规范.md 第 5 节）"
            )
        by_id[entry.id] = entry

    # 技术栈包前缀校验
    for _, name, _ in stacks:
        pack = packs[name]
        if not pack.prefix:
            continue
        for entry in pack.entries:
            if not entry.id.startswith(pack.prefix):
                raise BuildError(
                    f"条目前缀与包不一致：{entry.id} 出现在包 {pack.pack_id}"
                    f"（该包前缀应为 {pack.prefix}）"
                )
    for name, _ in domains:
        pack = packs[name]
        if not pack.prefix:
            continue
        for entry in pack.entries:
            if not entry.id.startswith(pack.prefix):
                raise BuildError(
                    f"条目前缀与包不一致：{entry.id} 出现在包 {pack.pack_id}"
                    f"（该包前缀应为 {pack.prefix}）"
                )
    return by_id, domain_priority


def apply_project_entries(root: Path, project: str, manifest: dict, by_id: dict) -> list[Entry]:
    """项目特有条目：manifest 的 project_only + 项目特有规范.md。"""
    added: list[Entry] = []
    prefix = f"STD-PRJ-{project.upper()}-"

    for item in (manifest.get("project_only") or []):
        if not isinstance(item, dict) or "id" not in item:
            raise BuildError("project_only 的每一项必须是含 `id` 的映射")
        eid = str(item["id"])
        if not eid.startswith(prefix):
            raise BuildError(f"项目特有条目 {eid} 的前缀必须是 {prefix}")
        body_parts = [str(item.get("content", "")).strip()]
        ex = item.get("examples") or {}
        if ex:
            body_parts.append(f"**正例**：{ex.get('good', '')}\n\n**反例**：{ex.get('bad', '')}")
        added.append(Entry(
            id=eid, title=str(item.get("category", "项目特有条目")), layer="project",
            source=project, origin_file="project.yaml",
            body="\n\n".join(p for p in body_parts if p),
            tier=str(item.get("tier", "indexed")), scope=str(item.get("scope", "项目特有约束")),
            frozen=bool(item.get("frozen", False)),
        ))

    spec_file = root / "projects" / project / "项目特有规范.md"
    if spec_file.is_file():
        parsed = parse_entries(read_text(spec_file), "project", project, "项目特有规范.md")
        for entry in parsed:
            if not entry.id.startswith(prefix):
                raise BuildError(
                    f"项目特有条目前缀不符：{entry.id}（见 projects/{project}/项目特有规范.md）\n"
                    f"  本项目条目的编号前缀必须是 {prefix}\n"
                    f"  若这是模板里的格式示例，把编号写成占位形式（如 {prefix}<序号>），"
                    f"它就不会被当成真实条目解析。"
                )
        added += parsed

    for entry in added:
        if entry.id in by_id:
            raise BuildError(
                f"项目特有条目编号重复：{entry.id}\n"
                f"  已存在：{by_id[entry.id].source} / {by_id[entry.id].origin_file}"
            )
        by_id[entry.id] = entry
    return added


def apply_overrides(manifest: dict, project: str, by_id: dict) -> list[dict]:
    """执行 override / disable / append。frozen 条目一律拒绝。"""
    records: list[dict] = []
    for raw in (manifest.get("overrides") or []):
        if not isinstance(raw, dict):
            raise BuildError("overrides 的每一项必须是映射")
        eid = str(raw.get("id", "")).strip()
        action = str(raw.get("action", "")).strip()
        reason = str(raw.get("reason", "")).strip()

        if action not in ("override", "disable", "append"):
            raise BuildError(f"override {eid}: action 必须是 override / disable / append")
        entry = by_id.get(eid)
        if entry is None:
            raise BuildError(f"override 引用了不存在的条目：{eid}")
        if not reason:
            raise BuildError(f"override {eid}: `reason` 必填（半年后靠它判断这条覆盖还要不要留）")
        if entry.frozen:
            extra = ""
            if action == "append":
                extra = (
                    "\n  注：append 同样被拒绝。追加内容可以实质架空原条目"
                    "（例如追加「本项目例外：…」），因此 frozen 条目不接受"
                    "任何形态的项目层修改。"
                )
            raise BuildError(
                f"禁止对 frozen 条目执行 {action}：{eid}\n"
                f"  frozen 表示不可协商（安全红线 / 编号体系 / 审计留痕）。"
                f"确需修改走知识库 Owner 流程，而不是在项目层绕过。{extra}"
            )

        if action == "disable":
            expires = raw.get("expires")
            if not expires:
                raise BuildError(f"disable {eid}: `expires` 必填（防止临时禁用变永久遗忘）")
            if entry.layer in ("baseline", "domain", "stack"):
                if not raw.get("approved_by"):
                    raise BuildError(
                        f"disable {eid}: 禁用「{LAYER_LABEL[entry.layer]}」条目需要 `approved_by`"
                    )
            entry.status = "disabled"
            entry.note = f"本项目禁用（批准：{raw.get('approved_by', '—')}，到期 {expires}）：{reason}"
        elif action == "override":
            entry.status = "overridden"
            entry.body = str(raw.get("content", "")).strip() or entry.body
            entry.note = f"本项目覆盖：{reason}"
        else:  # append
            entry.body = (entry.body + "\n\n**本项目追加**：" + str(raw.get("content", "")).strip()).strip()
            entry.status = "appended"
            entry.note = f"本项目追加：{reason}"

        records.append({"id": eid, "action": action, "layer": entry.layer, "reason": reason})

    return records


def resolve_conflicts(by_id: dict, domain_priority: dict) -> list[dict]:
    """处理条目显式声明的 conflicts_with。

    跨层冲突自动裁决（高层胜）；同层冲突要求 manifest 显式声明 domains 顺序，
    否则构建失败 —— 不允许工具静默挑一个。
    """
    records: list[dict] = []
    for entry in list(by_id.values()):
        for other_id in entry.conflicts_with:
            other = by_id.get(other_id)
            if other is None or other.status == "disabled" or entry.status == "disabled":
                continue
            a, b = sorted([entry, other], key=lambda e: (LAYER_RANK[e.layer], e.id))
            if a.id == b.id:
                continue
            if LAYER_RANK[a.layer] != LAYER_RANK[b.layer]:
                winner, loser = b, a          # 高层胜
                loser.status = "shadowed"
                loser.note = f"被 {winner.id} 按层级规则覆盖（{LAYER_LABEL[a.layer]} < {LAYER_LABEL[b.layer]}）"
                records.append({"winner": winner.id, "loser": loser.id, "rule": "层级优先"})
                continue
            # 同层冲突：必须由 manifest 的 domains 顺序裁决
            pa, pb = domain_priority.get(a.source), domain_priority.get(b.source)
            if pa is None or pb is None or pa == pb:
                raise BuildError(
                    f"同层条目冲突且无法裁决：{a.id}（{a.source}）与 {b.id}（{b.source}）\n"
                    f"  处理方式：在 project.yaml 的 domains 中显式声明两者的先后顺序。\n"
                    f"  不允许工具静默挑选 —— 静默裁决会产生无人能追溯的隐性债务。"
                )
            winner, loser = (a, b) if pa < pb else (b, a)
            loser.status = "shadowed"
            loser.note = f"被 {winner.id} 覆盖（{winner.source} 优先级高于 {loser.source}）"
            records.append({"winner": winner.id, "loser": loser.id, "rule": "领域包优先级"})
    return records


# ── 输出 ────────────────────────────────────────────────────

def compute_snapshot_hash(manifest_hash: str, entries: list) -> str:
    """快照哈希 —— 内容寻址，不是文件字节哈希。

    由「manifest 哈希 + 每条目的 id/层级/状态/正文哈希」算出，因此和输出格式无关：
    调整段落版式不会让它变，改一条规范就会让它变。这正是「这个批次用的是哪版规范」需要的性质。
    """
    parts = [manifest_hash]
    for e in sorted(entries, key=lambda x: (LAYER_RANK[x.layer], x.id)):
        parts.append(f"{e.id}|{e.layer}|{e.status}|{e.tier}|{e.frozen}|{sha256_of(e.body)}")
    return sha256_of("\n".join(parts))


def build_snapshot_md(project: str, manifest: dict, packs, stacks, domains,
                      entries: list[Entry], overrides, conflicts, manifest_hash) -> str:
    active = [e for e in entries if e.status in ("active", "appended", "overridden")]
    resident = [e for e in active if e.tier == "resident"]
    indexed = [e for e in active if e.tier != "resident"]
    changed = [e for e in entries if e.status in ("overridden", "appended", "disabled", "shadowed")]

    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %z")
    out: list[str] = []
    out.append(f"# 生效规范快照 · {project}\n")
    out.append(f"> 生成时间：{now}　｜　manifest hash：{manifest_hash}")
    out.append(f"> 快照哈希：{compute_snapshot_hash(manifest_hash, entries)}　（批次状态文件 `spec_snapshot.hash` 填这个值）")
    out.append("> **本文件由 ai-spec-build 生成，请勿手工编辑**——下次构建会覆盖。要改规范请改包或 manifest。\n")

    counts: dict[str, int] = {}
    for e in active:
        counts[e.layer] = counts.get(e.layer, 0) + 1
    summary = "　/　".join(f"{LAYER_LABEL[k]} {v}" for k, v in sorted(counts.items(), key=lambda kv: LAYER_RANK[kv[0]]))
    out.append(f"生效条目 **{len(active)}** 条（{summary}）；另有 {len(changed)} 条被覆盖或禁用。\n")

    out.append("## A. 常驻注入\n")
    out.append(f"_（{len(resident)} 条，预算 ≤{A_SECTION_BUDGET_LINES} 行。这 {len(resident)} 条是"
               "「不看就会做错」的规则，应注入项目 CLAUDE.md 常驻。）_\n")
    if not resident:
        out.append("_（无）_\n")
    for e in sorted(resident, key=lambda x: (LAYER_RANK[x.layer], x.id)):
        tag = {"overridden": " ← 已覆盖", "appended": " ← 本项目追加"}.get(e.status, "")
        src = "项目特有" if e.layer == "project" else e.source
        out.append(f"- **[{e.id}]** {e.title}（{src}）{tag}")
        line = e.rule_line()
        if line:
            out.append(f"  - {line}")
    out.append("")

    out.append("## B. 按需检索索引\n")
    out.append("_（其余条目。执行到具体任务时按「触发场景」读取条目原文，不要全量读。）_\n")
    out.append("| 条目 ID | 摘要 | 来源 | 触发场景 |")
    out.append("|---|---|---|---|")
    for e in sorted(indexed, key=lambda x: (LAYER_RANK[x.layer], x.id)):
        src = "项目特有" if e.layer == "project" else e.source
        out.append(f"| `{e.id}` | {e.title} | {src} | {e.scope or '—'} |")
    out.append("")

    out.append("## C. 来源链与裁决记录\n")
    out.append("_（审计用。回答「这条规则为什么是现在这个样子」。）_\n")
    if changed:
        out.append("| 条目 ID | 处置 | 来源 | 说明 |")
        out.append("|---|---|---|---|")
        for e in sorted(changed, key=lambda x: (LAYER_RANK[x.layer], x.id)):
            note = re.sub(r"\s+", " ", e.note).strip()
            out.append(f"| `{e.id}` | {e.status} | {e.source} | {note} |")
        out.append("")
    else:
        out.append("_（本次构建无覆盖、无追加、无禁用、无冲突裁决）_\n")

    out.append("## D. 项目声明摘要\n")
    out.append("| 维度 | 包 | 版本 | 状态 |")
    out.append("|---|---|---|---|")
    for key, name, version in stacks:
        out.append(f"| `{key}` | {name} | {version} | {packs[name].status} |")
    for name, version in domains:
        out.append(f"| domain | {name} | {version} | {packs[name].status} |")
    out.append("")
    out.append(f"- 领域包优先级（高 → 低）：{' > '.join(n for n, _ in domains) or '（无）'}")
    out.append(f"- 项目特有条目数：{counts.get('project', 0)}")
    if counts.get("project", 0) > MAX_PROJECT_ONLY_ITEMS:
        out.append(f"  - ⚠️ 超过 {MAX_PROJECT_ONLY_ITEMS} 条阈值：可能说明该项目的共性还没被抽象成包，"
                   "运行 `ai-spec-promote` 分析候选。")
    out.append("")
    return "\n".join(out)


def build_snapshot_json(project, manifest, packs, stacks, domains, entries,
                        overrides, conflicts, manifest_hash) -> str:
    doc = {
        "project": project,
        "manifest_hash": manifest_hash,
        "snapshot_hash": compute_snapshot_hash(manifest_hash, entries),
        "built_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "packs": ([{"dimension": "stack", "key": k, "pack": n, "version": v, "status": packs[n].status}
                   for k, n, v in stacks]
                  + [{"dimension": "domain", "pack": n, "version": v, "status": packs[n].status}
                     for n, v in domains]),
        "domain_priority": [n for n, _ in domains],
        "overrides": overrides,
        "conflict_resolutions": conflicts,
        "entries": [
            {
                "id": e.id, "title": e.title, "layer": e.layer,
                "layer_label": LAYER_LABEL[e.layer], "source": e.source,
                "origin_file": e.origin_file, "tier": e.tier, "scope": e.scope,
                "frozen": e.frozen, "status": e.status, "note": e.note,
            }
            for e in sorted(entries, key=lambda x: (LAYER_RANK[x.layer], x.id))
        ],
    }
    return json.dumps(doc, ensure_ascii=False, indent=2)


# ── 主流程 ──────────────────────────────────────────────────

def build_one(root: Path, packs: dict, project: str, check_only: bool, verbose: bool) -> int:
    manifest = load_manifest(root, project)
    manifest_hash = sha256_of(read_text(root / "projects" / project / "project.yaml"))

    stacks, domains = resolve_packs(manifest, packs, project)
    baseline = load_baseline(root)

    by_id, domain_priority = merge(packs, stacks, domains, baseline)
    apply_project_entries(root, project, manifest, by_id)
    overrides = apply_overrides(manifest, project, by_id)
    conflicts = resolve_conflicts(by_id, domain_priority)

    entries = list(by_id.values())
    md = build_snapshot_md(project, manifest, packs, stacks, domains, entries,
                           overrides, conflicts, manifest_hash)
    js = build_snapshot_json(project, manifest, packs, stacks, domains, entries,
                             overrides, conflicts, manifest_hash)

    # A 段预算检查
    a_lines = 0
    in_a = False
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

    active = [e for e in entries if e.status in ("active", "appended", "overridden")]
    if not check_only:
        out_dir = root / ".ai" / "spec-effective"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{project}.md").write_text(md, encoding="utf-8")
        (out_dir / f"{project}.json").write_text(js, encoding="utf-8")
        log = {
            "at": datetime.now(timezone.utc).astimezone().isoformat(),
            "project": project, "entries": len(active),
            "manifest_hash": manifest_hash,
            "snapshot_hash": compute_snapshot_hash(manifest_hash, entries),
            "overrides": len(overrides), "conflicts": len(conflicts),
        }
        logs = root / ".ai" / "logs" / "spec-build.jsonl"
        logs.parent.mkdir(parents=True, exist_ok=True)
        with logs.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(log, ensure_ascii=False) + "\n")

    print(f"✅ {project}：生效 {len(active)} 条"
          f"（常驻 {sum(1 for e in active if e.tier == 'resident')}）"
          f"，覆盖/禁用 {len(overrides)} 条"
          f"{'，冲突裁决 ' + str(len(conflicts)) + ' 条' if conflicts else ''}"
          f"{'  [--check，未写文件]' if check_only else ''}")
    if verbose:
        for key, name, version in stacks:
            print(f"     stack  {key:<4} {name}@{version} ({packs[name].status})")
        for name, version in domains:
            print(f"     domain      {name}@{version} ({packs[name].status})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="ai-spec-build · 规范编译器")
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
                    print(f"  {p.pack_id:<26} @{p.version:<8} {p.status:<9} "
                          f"{len(p.entries):>3} 条  {p.title}")
            print()
            return 0

        if args.all:
            projects = sorted(d.name for d in (root / "projects").iterdir()
                              if d.is_dir() and not d.name.startswith("_"))
            if not projects:
                print("未发现可编译的项目。\n")
                print("本仓库是通用资产，projects/ 下默认只有 _template/（模板不参与构建）。")
                print("接入第一个项目：\n")
                print("  cp -r projects/_template projects/<项目码>")
                print("  # 填 projects/<项目码>/project.yaml（选包 + 差异）")
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
