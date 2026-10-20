#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ai-gate-runner —— 统一门禁执行器

读取 `07_质量门禁/gates/*.md` 的定义，执行其中标注 `auto:<检查项 ID>` 的检查项，
把结果写回批次状态文件。

三条不能破的语义
----------------
1. **找不到检查项实现 → 整道门禁拒绝执行**，而不是跳过这一项。静默跳过等于门禁失效。
2. **`skip` 不等于 `pass`**。缺少校验材料（项目仓未挂载、依赖尚未实现的 Skill）时记为
   `skip`，转入人工确认。把"没法校验"当成"校验通过"，是门禁最容易失效的方式。
3. **执行器不代替人做判断**。`人` 标注的检查项原样列出，等人工确认；门禁不会自动变成
   `passed`——需要 `--confirm` 显式签核。

用法
----
  python3 gate_run.py --list-checks                    # 列出检查项库与实现状态
  python3 gate_run.py --project <码> --batch <批次号> --gate gate-03
  python3 gate_run.py --project <码> --batch <批次号> --all        # 按顺序跑到第一个未通过
  python3 gate_run.py ... --check                      # 只校验，不回写状态
  python3 gate_run.py ... --gate gate-03 --confirm --by 张三       # 人工签核通过
  python3 gate_run.py ... --gate gate-03 --waive --by 张三 --reason "..." --expires 2027-06-30

退出码：0 通过（passed / waived）｜ 1 未通过或待人工确认 ｜ 2 执行器自身错误
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("错误：缺少 PyYAML。安装：pip install pyyaml\n")
    sys.exit(2)

PASS, FAIL, SKIP = "pass", "fail", "skip"
DONE_STATES = {"done", "skipped", "failed"}
VALID_GATE_STATUS = {"pending", "passed", "failed", "waived", "pending_manual"}

# 产出物按路径关键词归类；项目文档仓的目录命名应与此一致
PATH_MARKERS = {
    "req": ("需求", "req", "prd", "requirement"),
    "design": ("设计", "design"),
    "test": ("测试", "test", "用例"),
    "deliver": ("交付", "上线", "发布", "release", "rollout"),
    "db": ("数据库", "db", "ddl", "schema"),
    "api": ("接口", "api", "openapi", "契约", "contract"),
    "prototype": ("原型", "prototype", "proto"),
}

SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "私钥内容"),
    (re.compile(r"(?i)\bpassword\s*[:=]\s*[\"']?([A-Za-z0-9!@#$%^&*_.\-]{6,})"),
     "明文 password"),
    (re.compile(r"(?i)\bsecret\s*[:=]\s*[\"']?([A-Za-z0-9!@#$%^&*_.\-]{8,})"),
     "明文 secret"),
    (re.compile(r"(?i)jdbc:[a-z0-9]+://[^\s\"']*password=([^&\s\"']+)"), "JDBC 连接串内密码"),
]
SECRET_ALLOWLIST = re.compile(r"[<{]$|\$\{|xxx|your|example|placeholder|\*\*\*|change_?me|见配置|环境变量", re.I)

TASK_RE = re.compile(r"^(feat|fix|perf|refactor|test|docs|chore|style)\(([^)]+)\):\s*(\S.*)$")
FN_RE = re.compile(r"FN-[A-Z0-9]+-\d{3}(?:-D\d+)?")
TC_RE = re.compile(r"TC-(FN-[A-Z0-9]+-\d{3}(?:-D\d+)?)-\d{2}")
REQ_RE = re.compile(r"REQ-[A-Z0-9]+-\d{3}")
DEC_RE = re.compile(r"DEC-[A-Z0-9]+-\d{3}")


class GateError(Exception):
    """执行器自身错误：定义解析失败、检查项未实现、批次文件缺失等。"""


# ─── 基础工具 ────────────────────────────────────────────────

def find_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "CLAUDE.md").is_file() and (p / "09_资产库").is_dir():
            return p
    raise GateError("未找到仓库根目录（需同时存在 CLAUDE.md 与 09_资产库/）")


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except OSError as e:
        raise GateError(f"无法读取 {p}: {e}")


def sha256_of(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def path_matches(rel_path: str, kind: str) -> bool:
    low = rel_path.lower()
    return any(m in low for m in PATH_MARKERS[kind])


def real_value(v) -> bool:
    """判断 manifest 字段是否已填真实值（而不是 <占位>）。"""
    if v is None:
        return False
    s = str(v).strip()
    return bool(s) and not s.startswith("<") and "填" not in s


# ─── 门禁定义解析 ────────────────────────────────────────────

@dataclass
class GateItem:
    no: int
    text: str
    how: str            # "auto:<check-id>" 或 "人"
    level: str          # BLOCK | WARN
    on_fail: str

    @property
    def is_auto(self) -> bool:
        return self.how.startswith("auto:")

    @property
    def check_id(self) -> str:
        return self.how.split(":", 1)[1].strip() if self.is_auto else ""


@dataclass
class Gate:
    gate_id: str
    title: str
    stage: str
    blocking: bool
    waivable: str       # yes | no | partial
    items: list[GateItem] = field(default_factory=list)
    path: Path | None = None


META_BLOCK = re.compile(r"^```\n(stage:.*?)\n```", re.S | re.M)
ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(BLOCK|WARN)\s*\|\s*(.+?)\s*\|\s*$")


def parse_gate(path: Path) -> Gate:
    text = read(path)
    m = META_BLOCK.search(text)
    if not m:
        raise GateError(f"{path}：缺少 ```stage/blocking/auto_check``` 元信息块")
    meta = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    for req in ("stage", "blocking", "auto_check", "waivable"):
        if req not in meta:
            raise GateError(f"{path}：元信息缺少 `{req}`")

    m2 = re.match(r"^(gate-\d{2})-", path.name)
    if not m2:
        raise GateError(f"{path}：文件名应为 gate-NN-<名称>.md")
    gate_id = m2.group(1)
    title = re.sub(r"^" + re.escape(gate_id) + r"\s*", "",
                   text.split("\n", 1)[0].lstrip("# ").strip())

    items = []
    for line in text.split("\n"):
        r = ROW_RE.match(line)
        if r:
            items.append(GateItem(int(r.group(1)), r.group(2), r.group(3),
                                  r.group(4), r.group(5)))
    if not items:
        raise GateError(f"{path}：未解析到检查项表格")

    return Gate(gate_id, title, meta["stage"], meta["blocking"] == "true",
                meta["waivable"], items, path)


def discover_gates(root: Path) -> dict[str, Gate]:
    gates = {}
    for p in sorted((root / "07_质量门禁" / "gates").glob("gate-*.md")):
        g = parse_gate(p)
        gates[g.gate_id] = g
    if not gates:
        raise GateError("未找到任何门禁定义（07_质量门禁/gates/gate-*.md）")
    return gates


# ─── 批次状态与索引 ──────────────────────────────────────────

@dataclass
class Ctx:
    root: Path
    project: str
    batch_id: str
    state_path: Path
    state: dict
    batch: dict                 # state 顶层
    repo_root: Path | None      # 项目仓（manifest.repo 指向）
    artifacts: list[dict]       # state.artifacts（已解析绝对路径）
    gate: Gate

    def gate_entry(self) -> dict:
        for g in self.batch.setdefault("gates", []):
            if g.get("id") == self.gate.gate_id:
                return g
        entry = {"id": self.gate.gate_id, "status": "pending"}
        self.batch["gates"].append(entry)
        return entry

    def artifact_texts(self, kind: str | None = None) -> list[tuple[str, str]]:
        out = []
        for a in self.artifacts:
            rel = a.get("rel", "")
            if kind and not path_matches(rel, kind):
                continue
            if a.get("abs") and a["abs"].is_file():
                out.append((rel, read(a["abs"])))
        return out

    def all_artifact_text(self) -> str:
        return "\n".join(t for _, t in self.artifact_texts())

    def repo_texts(self, exts=(".md", ".yml", ".yaml", ".sql")) -> list[tuple[str, str]]:
        if not self.repo_root or not self.repo_root.is_dir():
            return []
        out = []
        for p in sorted(self.repo_root.rglob("*")):
            if p.is_file() and p.suffix.lower() in exts and ".git" not in p.parts:
                try:
                    out.append((str(p.relative_to(self.repo_root)), p.read_text(encoding="utf-8")))
                except (OSError, UnicodeDecodeError):
                    continue
        return out

    def scoped_fns(self) -> list[str]:
        """本批次范围内的 FN：出现在产出物中、但排除编号总表本身。"""
        fns: set[str] = set()
        for rel, text in self.artifact_texts():
            if "功能编号总表" in rel:
                continue
            fns.update(FN_RE.findall(text))
        return sorted(fns)

    def parse_number_table(self) -> dict[str, list[dict]]:
        path = self.root / ".ai" / "index" / "功能编号总表.md"
        if not path.is_file():
            return {}
        sections, cur = {}, None
        for line in read(path).split("\n"):
            h = re.match(r"^##\s+(.+?)\s*$", line)
            if h:
                cur = h.group(1)
                sections[cur] = []
                continue
            if cur and line.startswith("|"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                if not cells or set("".join(cells)) <= set("-: "):
                    continue
                if cells[0] in ("编号", "表名", "项目码"):
                    sections[cur].append({"__header__": cells})
                else:
                    sections[cur].append({"cells": cells})
        return sections


def load_ctx(root: Path, project: str, batch_id: str, gate: Gate) -> Ctx:
    mpath = root / "projects" / project / "project.yaml"
    if not mpath.is_file():
        raise GateError(f"找不到项目 manifest：{mpath}")
    try:
        manifest = yaml.safe_load(read(mpath)) or {}
    except yaml.YAMLError as e:
        raise GateError(f"{mpath} 解析失败：{e}")

    spath = root / ".ai" / "state" / f"{batch_id}.yaml"
    if not spath.is_file():
        raise GateError(f"找不到批次状态文件：{spath}")
    try:
        state = yaml.safe_load(read(spath)) or {}
    except yaml.YAMLError as e:
        raise GateError(f"{spath} 解析失败：{e}")

    repo_root = None
    if real_value(manifest.get("repo")):
        cand = Path(str(manifest["repo"])).expanduser()
        repo_root = cand if cand.is_absolute() else (root.parent / cand)
        repo_root = repo_root.resolve()
        if not repo_root.is_dir():
            repo_root = None

    arts = []
    for a in (state.get("artifacts") or []):
        if not isinstance(a, dict) or "path" not in a:
            continue
        rel = str(a["path"])
        base = repo_root or root
        arts.append({**a, "rel": rel, "abs": (base / rel)})

    return Ctx(root, project, batch_id, spath, state, state, repo_root, arts, gate)


# ─── 检查项库 ────────────────────────────────────────────────
# 每个检查项返回 (result, detail)。result ∈ {pass, fail, skip}

CHECKS: dict[str, tuple[str, callable]] = {}


def check(cid: str, desc: str):
    def deco(fn):
        CHECKS[cid] = (desc, fn)
        return fn
    return deco


def _need_repo(ctx: Ctx, why: str):
    if not ctx.repo_root:
        return (SKIP, f"项目仓不可用（`projects/{ctx.project}/project.yaml` 的 `repo` 未填或路径不存在）。"
                      f"需在项目仓内执行：{why}")
    return None


def _need_docs(ctx: Ctx):
    if not ctx.artifacts:
        return (SKIP, "批次状态文件的 `artifacts` 为空，无产出物可校验。"
                      "请先让上游 Skill 登记产出物，或检查 `repo` 是否指向了正确的项目文档仓。")
    return None


@check("req-acceptance-quantified", "验收标准是否可量化")
def _c_req_acceptance(ctx: Ctx):
    if (s := _need_docs(ctx)):
        return s
    hits = [(r, t) for r, t in ctx.artifact_texts("req") if "验收" in t]
    if not hits:
        return (SKIP, "未在需求类产出物中找到「验收」章节，无法判断。请在需求文档中补验收要点。")
    bad = []
    for rel, t in hits:
        seg = t.split("验收", 1)[1][:2000]
        if not re.search(r"\d|\b不得\b|\b必须\b|\b禁止\b|\b返回\b|\b≤\b|\b>=\b", seg):
            bad.append(rel)
    if bad:
        return (FAIL, "以下产出物的验收要点未出现任何可判定要素（数字 / 阈值 / 状态码 / 强制词）："
                      + "、".join(bad))
    return (PASS, f"已在 {len(hits)} 份需求类产出物中检到可判定的验收要点。")


@check("fn-coverage-prototype", "原型是否覆盖全部 FN")
def _c_fn_cov_proto(ctx: Ctx):
    if (s := _need_repo(ctx, "在原型工程仓内确认每个 FN 都有对应页面元素")):
        return s
    marked: set[str] = set()
    for _, t in ctx.repo_texts((".html", ".vue", ".jsx", ".tsx", ".js")):
        marked.update(re.findall(r'data-fn=["\'](FN-[A-Z0-9]+-\d{3}(?:-D\d+)?)["\']', t))
    if not marked:
        return (SKIP, "项目仓内未检到任何 `data-fn` 标记，无法判断原型覆盖。"
                      "若原型在独立仓，请在 manifest 的 `repo` 指向原型工程仓。")
    fns = set(ctx.scoped_fns())
    missing = sorted(fns - marked)
    if missing:
        return (FAIL, "以下 FN 在原型中没有对应元素：" + "、".join(missing))
    return (PASS, f"范围内 {len(fns)} 个 FN 均在原型中有标记。")


@check("data-fn-markers", "原型是否存在可统计的 data-fn 标记")
def _c_data_fn(ctx: Ctx):
    if (s := _need_repo(ctx, "在原型工程仓内为可交互元素补 `data-fn=\"FN-...\"` 标记")):
        return s
    total, valid = 0, 0
    invalid = []
    for rel, t in ctx.repo_texts((".html", ".vue", ".jsx", ".tsx", ".js")):
        for raw in re.findall(r'data-fn=["\']([^"\']*)["\']', t):
            total += 1
            if FN_RE.fullmatch(raw.strip()):
                valid += 1
            else:
                invalid.append(f"{rel}: {raw}")
    if total == 0:
        return (FAIL, "项目仓内未检到任何 `data-fn` 标记。"
                      "原型元素不带标记，`ai-requirement-04-prd` 就无法靠遍历原型生成 PRD。")
    if invalid:
        return (FAIL, f"{len(invalid)} 处 `data-fn` 取值不是合法 FN 编号，例如：" + "；".join(invalid[:3]))
    return (PASS, f"检到 {valid} 处合法 `data-fn` 标记。")


@check("fn-coverage-design", "每个 FN 是否有对应设计章节")
def _c_fn_cov_design(ctx: Ctx):
    if (s := _need_docs(ctx)):
        return s
    fns = ctx.scoped_fns()
    if not fns:
        return (SKIP, "产出物中未检到任何 FN 编号，无法判断设计覆盖率。"
                      "请确认上游 `ai-requirement-02-analysis` 已分配 FN 编号。")
    design = "\n".join(t for _, t in ctx.artifact_texts("design"))
    if not design.strip():
        return (FAIL, f"范围内有 {len(fns)} 个 FN，但没有设计类产出物"
                      f"（路径需含 {'/'.join(PATH_MARKERS['design'])} 之一）。")
    missing = [f for f in fns if f not in design]
    if missing:
        return (FAIL, f"以下 {len(missing)} 个 FN 没有对应设计章节：" + "、".join(missing))
    return (PASS, f"范围内 {len(fns)} 个 FN 均有设计章节。")


@check("fn-design-section", "每个 FN 是否有专属设计小节")
def _c_fn_design_section(ctx: Ctx):
    """`fn-coverage-design` 的加强版。

    前者只要求 FN 出现在设计类产出物中——接口契约、数据库设计里提到该 FN 也算，
    所以是个偏松的下限。本检查要求 FN 在设计文档里**有专属小节**（标题或 § 引用），
    这才是「有对应设计章节」的字面含义。定为 WARN：命名习惯千差万别，
    误报不该阻断交付，但值得有人看一眼。
    """
    if (s := _need_docs(ctx)):
        return s
    fns = ctx.scoped_fns()
    if not fns:
        return (SKIP, "产出物中未检到任何 FN 编号，无法判断。")
    design = "\n".join(t for _, t in ctx.artifact_texts("design"))
    if not design.strip():
        return (SKIP, "无设计类产出物，无法判断。")
    missing = []
    for f in fns:
        pat = re.compile(r"^#{1,6}[^\n]*" + re.escape(f) + r"|§\s*" + re.escape(f), re.M)
        if not pat.search(design):
            missing.append(f)
    if missing:
        return (FAIL, f"{len(missing)} 个 FN 在设计文档中没有专属小节"
                      f"（既不是标题也不带 § 引用）：" + "、".join(missing[:8]))
    return (PASS, f"范围内 {len(fns)} 个 FN 在设计文档中均有专属小节。")


@check("api-has-fn", "每个接口是否可追溯到 FN")
def _c_api_has_fn(ctx: Ctx):
    if (s := _need_docs(ctx)):
        return s
    contracts = [(r, t) for r, t in ctx.artifact_texts("api")
                 if r.endswith((".yaml", ".yml", ".json"))]
    if not contracts:
        return (SKIP, "未找到接口契约文件（路径含 "
                      f"{'/'.join(PATH_MARKERS['api'])} 且扩展名为 yaml/yml/json）。")
    orphans, total = [], 0
    fns = set(ctx.scoped_fns())
    for rel, t in contracts:
        try:
            doc = yaml.safe_load(t) or {}
        except yaml.YAMLError as e:
            return (FAIL, f"{rel} 不是合法 YAML：{e}")
        for path, ops in (doc.get("paths") or {}).items():
            if not isinstance(ops, dict):
                continue
            for method, op in ops.items():
                if method.lower() not in ("get", "post", "put", "delete", "patch", "head", "options"):
                    continue
                total += 1
                if not isinstance(op, dict):
                    orphans.append(f"{method.upper()} {path}")
                    continue
                blob = json.dumps(op, ensure_ascii=False)
                if not (FN_RE.search(blob) or FN_RE.search(str(op.get("x-fn-id", "")))
                        or (fns and re.search(r"FN-", blob))):
                    orphans.append(f"{method.upper()} {path}")
    if orphans:
        return (FAIL, f"{len(orphans)}/{total} 个接口无法追溯到 FN（建议加 `x-fn-id` 扩展字段）："
                      + "；".join(orphans[:5]))
    return (PASS, f"{total} 个接口均可追溯到 FN。")


@check("api-error-codes", "每个接口是否定义了错误码")
def _c_api_err(ctx: Ctx):
    if (s := _need_docs(ctx)):
        return s
    contracts = [(r, t) for r, t in ctx.artifact_texts("api")
                 if r.endswith((".yaml", ".yml", ".json"))]
    if not contracts:
        return (SKIP, "未找到接口契约文件，无法判断错误码定义。")
    bad, total = [], 0
    for rel, t in contracts:
        try:
            doc = yaml.safe_load(t) or {}
        except yaml.YAMLError:
            continue
        for path, ops in (doc.get("paths") or {}).items():
            if not isinstance(ops, dict):
                continue
            for method, op in ops.items():
                if method.lower() not in ("get", "post", "put", "delete", "patch"):
                    continue
                total += 1
                if not isinstance(op, dict):
                    bad.append(f"{method.upper()} {path}")
                    continue
                codes = set((op.get("responses") or {}).keys())
                if op.get("x-error-codes"):
                    codes |= set(op["x-error-codes"]) if isinstance(op["x-error-codes"], (list, dict)) else codes
                has_err = any(str(c).startswith("4") or str(c).startswith("5") for c in codes)
                if not has_err:
                    bad.append(f"{method.upper()} {path}")
    if bad:
        return (FAIL, f"{len(bad)}/{total} 个接口未定义任何 4xx/5xx 响应（符合 STD-BASE-321）："
                      + "；".join(bad[:5]))
    return (PASS, f"{total} 个接口均定义了错误响应。")


@check("ddl-rollback", "数据库设计是否含 DDL 与回滚脚本")
def _c_ddl(ctx: Ctx):
    if (s := _need_docs(ctx)):
        return s
    hits = ctx.artifact_texts("db")
    if not hits:
        return (SKIP, "未找到数据库设计类产出物（路径需含 "
                      f"{'/'.join(PATH_MARKERS['db'])} 之一）。")
    blob = "\n".join(t for _, t in hits)
    has_ddl = re.search(r"(?i)\b(create\s+table|alter\s+table|create\s+index)\b", blob)
    has_rb = re.search(r"(?i)(回滚|rollback|roll_back|down\.sql|undo)", blob)
    if not has_ddl:
        return (FAIL, "数据库设计产出物中未检到 DDL（CREATE TABLE / ALTER TABLE）。")
    if not has_rb:
        return (FAIL, "数据库设计有 DDL 但未见回滚方案（符合 STD-BASE-311）："
                      "上线出问题时没有时间现场推导回滚语句。")
    return (PASS, "DDL 与回滚方案均已在数据库设计产出物中检到。")


@check("db-field-comments", "数据库字段是否有注释")
def _c_db_comment(ctx: Ctx):
    if (s := _need_docs(ctx)):
        return s
    hits = ctx.artifact_texts("db")
    if not hits:
        return (SKIP, "未找到数据库设计类产出物，无法判断字段注释。")
    blob = "\n".join(t for _, t in hits)
    if not re.search(r"(?i)create\s+table", blob):
        return (SKIP, "产出物中未检到 CREATE TABLE 语句，无法判断字段注释。")
    if re.search(r"(?i)comment\s+on\s+column", blob):
        return (PASS, "检到 `COMMENT ON COLUMN`（达梦的字段注释写法）。")
    tables = re.findall(r"(?is)create\s+table\s+(\S+)\s*\((.*?)\)\s*;", blob)
    if not tables:
        return (SKIP, "CREATE TABLE 语句格式无法解析，请人工核对字段注释。")
    missing = []
    for name, body in tables:
        for line in body.split("\n"):
            s = line.strip().rstrip(",")
            if not s or s.startswith("--") or re.match(r"(?i)^(primary|unique|foreign|constraint|key|index)\b", s):
                continue
            if "comment" not in s.lower():
                missing.append(f"{name}.{s.split()[0]}")
    if missing:
        return (FAIL, f"{len(missing)} 个字段没有注释（符合 STD-BASE-312），例如："
                      + "、".join(missing[:6]))
    return (PASS, f"{len(tables)} 张表的字段均有注释。")


@check("openapi-valid", "接口契约的 OpenAPI 结构是否合法")
def _c_openapi(ctx: Ctx):
    if (s := _need_docs(ctx)):
        return s
    contracts = [(r, t) for r, t in ctx.artifact_texts("api")
                 if r.endswith((".yaml", ".yml", ".json"))]
    if not contracts:
        return (SKIP, "未找到接口契约文件（OpenAPI），无法校验。"
                      "建议在 CI 中追加完整校验器：npx @redocly/cli lint <契约文件>")
    problems = []
    for rel, t in contracts:
        try:
            doc = yaml.safe_load(t) or {}
        except yaml.YAMLError as e:
            problems.append(f"{rel} 不是合法 YAML（{e}）"); continue
        if not isinstance(doc, dict):
            problems.append(f"{rel} 顶层不是映射"); continue
        if not ("openapi" in doc or "swagger" in doc):
            problems.append(f"{rel} 缺少 `openapi` / `swagger` 版本字段")
        if not doc.get("info", {}).get("title"):
            problems.append(f"{rel} 缺少 `info.title`")
        paths = doc.get("paths")
        if not isinstance(paths, dict) or not paths:
            problems.append(f"{rel} 缺少 `paths` 或为空"); continue
        for p, ops in paths.items():
            if not p.startswith("/"):
                problems.append(f"{rel} 路径 `{p}` 未以 / 开头")
            if not isinstance(ops, dict):
                problems.append(f"{rel} `{p}` 下没有操作定义"); continue
            for m, op in ops.items():
                if m.lower() not in ("get", "post", "put", "delete", "patch", "head", "options"):
                    continue
                if not isinstance(op, dict) or not op.get("responses"):
                    problems.append(f"{rel} {m.upper()} {p} 缺少 `responses`")
    if problems:
        return (FAIL, f"契约结构问题 {len(problems)} 处：" + "；".join(problems[:5]))
    return (PASS, f"{len(contracts)} 份契约通过结构校验。"
                  "（完整规范校验建议在 CI 中跑 `@redocly/cli lint`）")


@check("decision-recorded", "关键设计决策是否记录了理由")
def _c_decision(ctx: Ctx):
    if (s := _need_docs(ctx)):
        return s
    design = "\n".join(t for _, t in ctx.artifact_texts("design"))
    if not design.strip():
        return (SKIP, "无设计类产出物，无法判断决策记录。")
    decs = sorted(set(DEC_RE.findall(design)))
    if not decs:
        return (FAIL, "设计产出物中未见任何 `DEC` 编号。"
                      "关键决策不记录理由，半年后没人敢改它——参见 `09_资产库/领域模型/业务实体字典.md` 的同类论述。")
    return (PASS, f"检到 {len(decs)} 条设计决策记录：{', '.join(decs[:5])}")


@check("commit-format", "提交信息格式与 FN 关联")
def _c_commit_fmt(ctx: Ctx):
    if (s := _need_repo(ctx, "在项目仓内提交代码后重跑本门禁")):
        return s
    log = git_log(ctx.repo_root, 30)
    if log is None:
        return (SKIP, "项目仓不是 git 仓库或无法读取提交历史。")
    if not log:
        return (SKIP, "项目仓没有任何提交。")
    bad = []
    for h, subject, body in log:
        m = TASK_RE.match(subject)
        if not m:
            bad.append(f"{h} 「{subject[:40]}」类型或格式不符")
        elif not (FN_RE.search(subject) or FN_RE.search(body)):
            bad.append(f"{h} 「{subject[:40]}」未关联 FN 编号")
    if bad:
        return (FAIL, f"{len(bad)}/{len(log)} 个提交不合规（符合 STD-BASE-002 / 003）："
                      + "；".join(bad[:4]))
    return (PASS, f"最近 {len(log)} 个提交格式合规且均关联 FN 编号。")


@check("fn-has-commit", "每个 FN 是否有对应提交")
def _c_fn_commit(ctx: Ctx):
    if (s := _need_repo(ctx, "在项目仓内提交代码后重跑本门禁")):
        return s
    log = git_log(ctx.repo_root, 200)
    if log is None:
        return (SKIP, "项目仓不是 git 仓库或无法读取提交历史。")
    fns = ctx.scoped_fns()
    if not fns:
        return (SKIP, "产出物中未检到 FN 编号，无法判断提交关联。")
    blob = "\n".join(f"{s}\n{b}" for _, s, b in log)
    missing = [f for f in fns if f not in blob]
    if missing:
        return (FAIL, f"以下 {len(missing)} 个 FN 没有任何提交关联：" + "、".join(missing[:8]))
    return (PASS, f"范围内 {len(fns)} 个 FN 均有提交关联。")


@check("lint-passthrough", "编码静态检查")
def _c_lint(ctx: Ctx):
    return (SKIP, "静态检查需在项目仓内按该项目自己的配置执行，不在本执行器职责内。"
                  "请在项目仓执行其 lint 命令（如 `mvn -q verify`、`npm run lint`），"
                  "将结果附在评审记录中，再用 `--confirm` 签核本项。")


@check("unit-coverage-report", "单元测试覆盖率")
def _c_coverage(ctx: Ctx):
    return (SKIP, "覆盖率需项目侧的测试报告产出（属于 `ai-dev-04-unittest` / `ai-test-*` 的职责，"
                  "当前为 P1/P2 未实现）。项目侧执行测试并生成报告后，用 `--confirm` 签核本项。")


@check("secrets-externalized", "配置与密钥是否外置")
def _c_secrets(ctx: Ctx):
    if (s := _need_repo(ctx, "在项目仓内扫描配置与密钥")):
        return s
    found = []
    for rel, text in ctx.repo_texts((".yml", ".yaml", ".properties", ".env", ".json", ".xml", ".pem", ".key", ".md")):
        if any(seg in rel.lower() for seg in ("/test/", "/tests/", "example", "sample", "readme")):
            continue
        for pat, label in SECRET_PATTERNS:
            for m in pat.finditer(text):
                val = m.group(1) if m.groups() else ""
                if val and SECRET_ALLOWLIST.search(val):
                    continue
                line = text[:m.start()].count("\n") + 1
                found.append(f"{rel}:{line} {label}")
    if found:
        return (FAIL, f"检到 {len(found)} 处疑似硬编码凭据（符合 STD-BASE-104，"
                      f"进入 Git 历史后只能轮换密钥）：" + "；".join(found[:5]))
    return (PASS, "未检到疑似硬编码凭据。")


@check("fn-has-testcase", "每个 FN 是否有测试用例覆盖")
def _c_fn_tc(ctx: Ctx):
    if (s := _need_docs(ctx)):
        return s
    fns = ctx.scoped_fns()
    if not fns:
        return (SKIP, "产出物中未检到 FN 编号，无法判断用例覆盖。")
    covered = set(TC_RE.findall(ctx.all_artifact_text()))
    missing = [f for f in fns if f not in covered]
    if missing:
        return (FAIL, f"以下 {len(missing)} 个 FN 没有挂载用例（符合 STD-BASE-501）："
                      + "、".join(missing[:8]))
    return (PASS, f"范围内 {len(fns)} 个 FN 均有挂载用例。")


@check("testcase-executed", "用例执行率")
def _c_tc_exec(ctx: Ctx):
    """解析测试报告的「用例执行率」字段。

    字段名与两种写法由 `ai-test-05-report` 固定（`用例执行率：100%` 或表行 `| 用例执行率 | 100% |`）。
    找不到字段时记 `skip` 而不是 `pass`——"没法校验"和"校验通过"是两件事。
    """
    if (s := _need_docs(ctx)):
        return s
    docs = ctx.artifact_texts()
    if not docs:
        return (SKIP, "无产出物可查。")
    found_report = False
    for rel, t in docs:
        if "测试报告" not in rel and "用例执行率" not in t:
            continue
        m = (re.search(r"用例执行率[：:]\s*([\d.]+)\s*%", t)
             or re.search(r"\|\s*用例执行率\s*\|\s*([\d.]+)\s*%\s*\|", t))
        if not m:
            continue
        found_report = True
        try:
            rate = float(m.group(1))
        except ValueError:
            continue
        if rate >= 99.995:
            return (PASS, f"{rel}：用例执行率 {rate:g}%。")
        missed = re.search(r"未执行[^|\n]*?(\d+)\s*条", t)
        extra = f"，未执行 {missed.group(1)} 条" if missed else ""
        return (FAIL, f"{rel}：用例执行率 {rate:g}%{extra}。"
                      f"核心路径未跑完的情况下不应进入上线判断。")
    if found_report:
        return (FAIL, "测试报告存在但「用例执行率」取值无法解析，请按 "
                      "`ai-test-05-report` 约定的两种写法之一填写。")
    return (SKIP, "未找到测试报告（含「用例执行率」字段的产出物）。"
                  "该字段由 `ai-test-05-report` 产出；报告未生成或字段名被改动时无法自动校验。")


@check("p0p1-closed", "P0/P1 缺陷是否关闭")
def _c_defects(ctx: Ctx):
    """解析缺陷台账，检查 P0/P1 是否全部关闭。

    表头与状态取值由 `ai-test-03-execute` 固定。表头不符时记 `skip` 并说明——
    不猜测列含义，因为猜错会把"有未关闭的 P0"误报成通过。
    """
    if (s := _need_docs(ctx)):
        return s
    ledger = [(r, t) for r, t in ctx.artifact_texts()
              if "缺陷台账" in r or "缺陷" in r and "| 编号 |" in t]
    if not ledger:
        return (SKIP, "未找到缺陷台账。该产出由 `ai-test-03-execute` 生成；"
                      "未生成时无法判断缺陷是否收敛。")

    CLOSED = ("已关闭", "关闭", "closed", "已验证", "已转待办", "已废弃")
    for rel, t in ledger:
        lines = [l for l in t.split("\n") if l.strip().startswith("|")]
        header, rows = None, []
        for line in lines:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if header is None:
                header = cells
                continue
            rows.append(cells)
        if not header:
            continue
        if "级别" not in header or "状态" not in header:
            return (SKIP, f"{rel}：表头缺少「级别」或「状态」列，无法解析。"
                          f"表头格式见 `ai-test-03-execute` 的产出契约。")
        lv_i, st_i = header.index("级别"), header.index("状态")
        id_i = header.index("编号") if "编号" in header else 0
        open_blocks = []
        for cells in rows:
            if max(lv_i, st_i, id_i) >= len(cells):
                continue
            level, status = cells[lv_i].upper(), cells[st_i]
            if level not in ("P0", "P1"):
                continue
            if not any(c in status for c in CLOSED):
                open_blocks.append(f"{cells[id_i]}（{level}，{status}）")
        if open_blocks:
            return (FAIL, f"{rel}：{len(open_blocks)} 个 P0/P1 未关闭——"
                          + "、".join(open_blocks[:5]))
        return (PASS, f"{rel}：未关闭的 P0/P1 缺陷为 0。")
    return (SKIP, "缺陷台账中未解析到任何数据行，无法判断。")


@check("regression-scoped", "回归范围是否圈定")
def _c_regression(ctx: Ctx):
    if (s := _need_docs(ctx)):
        return s
    blob = ctx.all_artifact_text()
    if "回归" not in blob:
        return (FAIL, "产出物中未见回归范围说明。"
                      "`ai-test-04-regression`（P2）未实现前，需人工圈定并记录回归范围。")
    return (PASS, "产出物中已包含回归范围说明。")


@check("rollout-plan-present", "上线步骤与回滚方案")
def _c_rollout(ctx: Ctx):
    if (s := _need_docs(ctx)):
        return s
    hits = ctx.artifact_texts("deliver")
    if not hits:
        return (FAIL, f"没有交付类产出物（路径需含 {'/'.join(PATH_MARKERS['deliver'])} 之一）。"
                      "上线步骤与回滚方案缺失时，出问题只能现场推导。")
    blob = "\n".join(t for _, t in hits)
    if "回滚" not in blob and "rollback" not in blob.lower():
        return (FAIL, "交付类产出物中未见回滚方案。")
    return (PASS, f"已在 {len(hits)} 份交付类产出物中检到回滚方案。")


@check("orphan-fn-no-req", "是否存在无 REQ 来源的 FN")
def _c_orphan_req(ctx: Ctx):
    sec = ctx.parse_number_table()
    fn_sec = sec.get("功能点", [])
    rows = [r for r in fn_sec if "cells" in r]
    if not rows:
        return (SKIP, "功能编号总表的「功能点」段为空，无法判断。"
                      "`ai-requirement-02-analysis` 尚未登记编号时属正常。")
    header = next((r["__header__"] for r in fn_sec if "__header__" in r), [])
    src_i = header.index("来源 REQ") if "来源 REQ" in header else None
    if src_i is None:
        return (SKIP, "功能编号总表的「功能点」段缺少「来源 REQ」列，无法判断。"
                      "请按 `.ai/index/功能编号总表.md` 的表头补上该列。")
    orphans = []
    for r in rows:
        cells = r["cells"]
        fn = cells[0].strip("` ")
        if not FN_RE.fullmatch(fn):
            continue
        src = cells[src_i] if src_i < len(cells) else ""
        if not REQ_RE.search(src or ""):
            orphans.append(fn)
    if orphans:
        return (FAIL, f"{len(orphans)} 个 FN 没有来源 REQ（符合 STD-BASE-202）：" + "、".join(orphans[:8]))
    return (PASS, f"总表中 {len(rows)} 行功能点均有来源 REQ。")


@check("no-orphan-ids", "编号总表中是否有孤儿编号")
def _c_no_orphan(ctx: Ctx):
    sec = ctx.parse_number_table()
    rows = [r for r in sec.get("功能点", []) if "cells" in r]
    if not rows:
        return (SKIP, "功能编号总表的「功能点」段为空，无编号可判断。")
    fns = []
    for r in rows:
        fn = r["cells"][0].strip("` ")
        if FN_RE.fullmatch(fn):
            fns.append(fn)
    blob = ctx.all_artifact_text()
    orphans = [f for f in fns if f not in blob]
    if orphans:
        return (FAIL, f"{len(orphans)} 个编号登记在总表但任何产出物都未引用："
                      + "、".join(orphans[:8]))
    return (PASS, f"总表中 {len(fns)} 个编号均被产出物引用。")


@check("state-steps-final", "批次状态是否完整且已终态化")
def _c_state(ctx: Ctx):
    steps = ctx.batch.get("steps") or []
    if not steps:
        return (FAIL, "批次状态文件没有 `steps` 段。")
    bad = [s for s in steps if s.get("status") not in DONE_STATES]
    names = [s.get("name") for s in steps]
    if ctx.batch.get("current_step") not in names:
        return (FAIL, f"`current_step`（{ctx.batch.get('current_step')!r}）不在 steps 中：{names}")
    if bad:
        return (FAIL, f"{len(bad)} 个步骤未终态化："
                      + "、".join(f"{s.get('name')}({s.get('status')})" for s in bad))
    return (PASS, f"{len(steps)} 个步骤均已终态化。")


@check("artifacts-exist", "产出物是否齐备且未被外部修改")
def _c_artifacts(ctx: Ctx):
    arts = ctx.artifacts
    if not arts:
        return (SKIP, "批次状态文件的 `artifacts` 为空，无产出物可核对。")
    missing, mismatch = [], []
    for a in arts:
        p = a.get("abs")
        if not p or not p.is_file():
            missing.append(a.get("rel")); continue
        h = a.get("hash")
        if h and str(h).startswith("sha256:"):
            if sha256_of(read(p)) != h:
                mismatch.append(a.get("rel"))
    if missing:
        return (FAIL, f"{len(missing)} 个产出物文件不存在：" + "、".join(missing[:6]))
    if mismatch:
        return (FAIL, f"{len(mismatch)} 个产出物哈希与登记值不一致（被外部修改过）："
                      + "、".join(mismatch[:6]) + "。请确认是否重跑上游步骤。")
    return (PASS, f"{len(arts)} 个产出物齐备，哈希一致。")


def git_log(repo: Path, limit: int):
    try:
        r = subprocess.run(["git", "-C", str(repo), "log", f"-n{limit}", "--format=%H%x1f%s%x1f%b%x1e"],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    out = []
    for rec in r.stdout.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        parts = rec.split("\x1f")
        if len(parts) >= 2:
            out.append((parts[0][:7], parts[1], parts[2] if len(parts) > 2 else ""))
    return out


# ─── 执行与汇总 ──────────────────────────────────────────────

def run_gate(ctx: Ctx, write: bool, confirm: bool, by: str,
             waive: bool, reason: str, expires: str) -> tuple[str, list, list]:
    gate = ctx.gate
    results, manual = [], []

    for item in gate.items:
        if not item.is_auto:
            manual.append({"no": item.no, "text": item.text, "level": item.level})
            continue
        if item.check_id not in CHECKS:
            raise GateError(
                f"{gate.gate_id} 第 {item.no} 项引用了未实现的检查项 `{item.check_id}`。\n"
                f"  执行器拒绝执行整道门禁——静默跳过这一项等于门禁失效。\n"
                f"  可用检查项见：gate_run.py --list-checks"
            )
        fn = CHECKS[item.check_id][1]
        try:
            result, detail = fn(ctx)
        except GateError:
            raise
        except Exception as e:  # 检查项自身异常不能伪装成 pass
            result, detail = FAIL, f"检查项执行异常：{type(e).__name__}: {e}"
        results.append({"no": item.no, "id": item.check_id, "text": item.text,
                        "level": item.level, "result": result, "detail": detail})

    block_fail = [r for r in results if r["level"] == "BLOCK" and r["result"] == FAIL]
    warn_fail = [r for r in results if r["level"] == "WARN" and r["result"] == FAIL]
    skipped = [r for r in results if r["result"] == SKIP]

    if block_fail:
        status = "failed"
    elif waive:
        status = "waived"
    elif confirm:
        status = "passed"
    elif manual or skipped:
        status = "pending_manual"
    else:
        status = "passed"

    entry = ctx.gate_entry()
    if write:
        entry.update({
            "status": status,
            "at": now_iso(),
            "by": by if (confirm or waive) else "auto",
            "note": (f"豁免：{reason}（到期 {expires}）" if waive
                     else (f"人工签核通过" if confirm else
                           f"BLOCK 失败 {len(block_fail)} 项" if block_fail else
                           f"待人工确认 {len(manual) + len(skipped)} 项")),
            "checks": results,
            "manual_pending": [m["text"] for m in manual],
        })
        if waive:
            ctx.batch.setdefault("waivers", []).append({
                "gate": gate.gate_id, "reason": reason, "approved_by": by,
                "at": now_iso(), "review_at": expires,
            })
        ctx.state_path.write_text(
            yaml.safe_dump(ctx.batch, allow_unicode=True, sort_keys=False, width=100),
            encoding="utf-8")
        log = ctx.root / ".ai" / "logs" / f"{ctx.batch_id}.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "at": now_iso(), "gate": gate.gate_id, "status": status,
                "block_fail": len(block_fail), "warn_fail": len(warn_fail),
                "skipped": len(skipped), "manual": len(manual), "by": entry["by"],
            }, ensure_ascii=False) + "\n")

    return status, results, manual


ICON = {PASS: "✅", FAIL: "❌", SKIP: "⏭️ "}


def report(ctx: Ctx, status: str, results, manual, write: bool) -> None:
    g = ctx.gate
    print(f"\n门禁：{g.gate_id} {g.title}")
    print(f"批次：{ctx.batch_id}　｜　阶段：{g.stage}　｜　waivable: {g.waivable}")
    print(f"结果：{status}\n")

    for r in results:
        print(f"  {ICON.get(r['result'], '?')} [{r['no']}] {r['text']}")
        if r["result"] != PASS:
            print(f"       {r['detail']}")

    if manual:
        print(f"\n  ── 需人工核对（{len(manual)} 项，执行器不替你拍板）──")
        for m in manual:
            print(f"     [{m['no']}] ({m['level']}) {m['text']}")

    skipped = [r for r in results if r["result"] == SKIP]
    if skipped:
        print(f"\n  ⚠️  {len(skipped)} 项无法自动校验（skip ≠ pass）。"
              f"补齐材料或人工确认后再签核。")

    if status == "failed":
        print("\n  → 门禁不通过，不可进入下一阶段。修正 BLOCK 项后重跑。")
    elif status == "pending_manual":
        print(f"\n  → 待人工确认。核对上方清单后执行：")
        print(f"     python3 {Path(__file__).name} --project {ctx.project} --batch {ctx.batch_id} "
              f"--gate {g.gate_id} --confirm --by <你的名字>")
    elif status == "passed":
        print("\n  → 门禁通过。")
    elif status == "waived":
        print("\n  → 门禁已豁免（已记入 waivers，到期自动复查）。")
    if not write:
        print("\n  （--check：未回写状态文件）")


def main() -> int:
    ap = argparse.ArgumentParser(description="ai-gate-runner · 统一门禁执行器")
    ap.add_argument("--project")
    ap.add_argument("--batch", help="批次号（.ai/state/<批次号>.yaml）")
    ap.add_argument("--gate", help="门禁 id，如 gate-03；省略则按顺序跑到第一个未通过")
    ap.add_argument("--all", action="store_true", help="按顺序执行全部门禁，遇到未通过即停")
    ap.add_argument("--check", action="store_true", help="只校验，不回写状态文件")
    ap.add_argument("--confirm", action="store_true", help="人工签核通过")
    ap.add_argument("--waive", action="store_true", help="豁免本门禁")
    ap.add_argument("--reason", default="", help="豁免原因（--waive 必填）")
    ap.add_argument("--expires", default="", help="豁免复查日期 YYYY-MM-DD（--waive 必填）")
    ap.add_argument("--by", default="", help="签核 / 豁免人")
    ap.add_argument("--list-checks", action="store_true", help="列出检查项库")
    ap.add_argument("--repo", help="仓库根目录（默认自动向上查找）")
    args = ap.parse_args()

    try:
        root = Path(args.repo).resolve() if args.repo else find_root(Path(__file__).resolve())

        if args.list_checks:
            gates = discover_gates(root)
            used = {it.check_id for g in gates.values() for it in g.items if it.is_auto}
            print(f"\n检查项库（共 {len(CHECKS)} 项；门禁定义引用 {len(used)} 项）\n")
            for cid in sorted(CHECKS):
                mark = "被引用" if cid in used else "未引用"
                print(f"  {cid:<26} {mark}  {CHECKS[cid][0]}")
            missing = sorted(used - set(CHECKS))
            if missing:
                print("\n❌ 门禁引用了未实现的检查项：" + ", ".join(missing))
                return 2
            print("\n✅ 门禁定义引用的检查项均已实现\n")
            return 0

        if not args.project or not args.batch:
            ap.error("需要 --project 与 --batch（或 --list-checks）")

        gates = discover_gates(root)
        order = sorted(gates)
        if args.gate:
            if args.gate not in gates:
                raise GateError(f"未找到门禁 {args.gate}；可用：{', '.join(order)}")
            targets = [args.gate]
        elif args.all:
            targets = order
        else:
            ap.error("需要 --gate <id> 或 --all")

        if args.waive:
            if not args.reason or not args.expires:
                raise GateError("--waive 必须同时提供 --reason 与 --expires（豁免不自动续期）")
            if not args.by:
                raise GateError("--waive 必须提供 --by（豁免必须留痕到人）")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.expires):
                raise GateError("--expires 需为 YYYY-MM-DD")
        if (args.confirm or args.waive) and not args.by:
            raise GateError("--confirm / --waive 必须提供 --by")

        worst = 0
        for gid in targets:
            gate = gates[gid]
            # 顺序前置校验：上一道门禁必须已通过或豁免
            idx = order.index(gid)
            if idx > 0:
                prev = order[idx - 1]
                ctx0 = load_ctx(root, args.project, args.batch, gates[prev])
                st = next((x.get("status") for x in (ctx0.batch.get("gates") or [])
                           if x.get("id") == prev), "pending")
                if st not in ("passed", "waived"):
                    print(f"\n⛔ 拒绝执行 {gid}：上一道 {prev} 的状态为 `{st}`。"
                          f"\n   门禁不允许跳步。先完成 {prev}。\n")
                    return 2

            if gate.waivable == "no" and args.waive:
                raise GateError(f"{gate.gate_id} 的 `waivable` 为 no，不允许豁免。\n"
                                f"  该门禁守着一个跳过就无法补救的东西（见门禁文件的「豁免机制」段）。")
            if gate.waivable == "partial" and args.waive:
                print(f"⚠️  {gate.gate_id} 为 partial 豁免：通过标准中标注为不可豁免的项仍需人工确认。")

            ctx = load_ctx(root, args.project, args.batch, gate)
            status, results, manual = run_gate(
                ctx, write=not args.check, confirm=args.confirm, by=args.by,
                waive=args.waive, reason=args.reason, expires=args.expires)
            report(ctx, status, results, manual, write=not args.check)

            if status in ("failed", "pending_manual"):
                worst = 1
                if args.all and status == "failed":
                    print(f"\n按顺序执行中止于 {gid}。")
                    break
            elif status in ("passed", "waived") and args.all:
                continue
        return worst
    except GateError as e:
        sys.stderr.write(f"\n❌ {e}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
