#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 .claude/skills/ 挂载层

## 为什么需要这一层

知识库里的 36 个「Skill」原本只是 Markdown 文件——没有被 Claude 的 skill 机制发现。
使用者必须知道路径、手动让 AI 去读，这正是不好上手的原因。

Claude 靠 `.claude/skills/<name>/SKILL.md` 的 frontmatter（`name` + `description`）决定
「什么时候该用哪个 skill」。所以要让这些 Skill 真正可用，需要把它们挂到那个位置。

## 为什么是生成而不是手写

挂载层只是**指针**，真实定义在知识库的三件套里。手写会产生 36 份需要同步的副本，
而副本一定会与真实定义分叉——这个仓库里已经反复出现过这类问题。

生成还有一个好处：`--check` 模式可以在 CI 或一致性检查里验证挂载层是否与真实定义同步。

用法：
  python3 00_工作空间配置/scripts/build_claude_skills.py          # 生成/更新
  python3 00_工作空间配置/scripts/build_claude_skills.py --check   # 只校验是否同步

退出码：0 成功或已同步 ｜ 1 不同步（--check）｜ 2 脚本自身错误
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("错误：缺少 PyYAML。安装：pip install pyyaml\n")
    sys.exit(2)

GENERATED_NOTE = ("> 本文件由 `00_工作空间配置/scripts/build_claude_skills.py` **生成**，不要手改。\n"
                  "> 要改这个 Skill，改它的真实定义后重跑该脚本。\n")


def find_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "CLAUDE.md").is_file() and (p / "09_资产库").is_dir():
            return p
    raise SystemExit("未找到仓库根目录")


def read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        raise SystemExit(f"{path}：缺少 frontmatter")
    return yaml.safe_load(m.group(1)) or {}


def shell_body(name: str, rel: str, description: str) -> str:
    return f"""---
name: {name}
description: {description}
---

# {name}

{GENERATED_NOTE}
完整定义在知识库中（`{rel}`）：

| 内容 | 文件 |
|---|---|
| 契约与前置条件 | `{rel}/SKILL.md` |
| **执行指令** | `{rel}/prompt.md` |
| 知识索引 | `{rel}/references/INDEX.md` |

## 执行方式

1. 读 `{rel}/SKILL.md`，**逐条核对「前置条件」**——不满足就停下并说明是哪一条不满足，
   不要"先跑跑看"
2. 读 `{rel}/prompt.md`，**按它执行**。它是这个 Skill 的指令本体
3. `references/` 默认只加载 `INDEX.md`，按它的「何时读取」列按需读取，单次不超过 3 个文件
4. 产出物按 `SKILL.md` 的产出契约落位，并登记到批次状态文件 `projects/<项目码>/.agent/state/<批次号>.yaml` 的 `artifacts`

## 为什么要经过这一层

这层是**指针**：真实定义只有一份（在上面的路径里），这里是给 Claude 的 skill 发现机制看的入口。
把内容复制到这里会产生需要同步的副本，而副本一定会分叉——
所以本文件是生成的，`--check` 模式可以验证它是否与真实定义一致。
"""


def collect(root: Path):
    out = []
    for p in sorted(root.rglob("SKILL.md")):
        rel_parts = p.relative_to(root).parts
        if rel_parts[0] in (".git", ".claude", "projects"):
            continue
        meta = read_frontmatter(p)
        name = meta.get("name")
        desc = meta.get("description")
        if not name or not desc:
            print(f"  ⚠️ {p}：缺 name 或 description，跳过（它是 skill 发现的前提）")
            continue
        out.append((name, desc, p.parent.relative_to(root).as_posix()))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 .claude/skills/ 挂载层")
    ap.add_argument("--check", action="store_true", help="只校验是否与真实定义同步")
    ap.add_argument("--repo", help="仓库根目录")
    args = ap.parse_args()

    root = Path(args.repo).resolve() if args.repo else find_root(Path(__file__).resolve())
    skills = collect(root)
    out_dir = root / ".claude" / "skills"

    if args.check:
        problems = []
        for name, desc, rel in skills:
            target = out_dir / name / "SKILL.md"
            if not target.is_file():
                problems.append(f"{name}：挂载层缺失")
                continue
            text = target.read_text(encoding="utf-8")
            m = re.search(r"^description: (.+)$", text, re.M)
            if not m or m.group(1).strip() != desc.strip():
                problems.append(f"{name}：description 与真实定义不一致")
            if rel not in text:
                problems.append(f"{name}：挂载层未指向真实定义路径 {rel}")
        existing = {d.name for d in out_dir.iterdir() if d.is_dir()} if out_dir.is_dir() else set()
        for stale in sorted(existing - {n for n, _, _ in skills}):
            problems.append(f"{stale}：挂载层存在但知识库里已无此 Skill")
        if problems:
            print(f"\n❌ 挂载层与真实定义不同步（{len(problems)} 处）：")
            for x in problems[:15]:
                print(f"   {x}")
            print("\n   修复：python3 00_工作空间配置/scripts/build_claude_skills.py\n")
            return 1
        print(f"\n✅ 挂载层与真实定义一致（{len(skills)} 个 Skill）\n")
        return 0

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    for name, desc, rel in skills:
        d = out_dir / name
        d.mkdir()
        (d / "SKILL.md").write_text(shell_body(name, rel, desc), encoding="utf-8")
    print(f"\n✅ 已生成 {len(skills)} 个 skill 挂载到 .claude/skills/")
    print("   真实定义仍在知识库的 <域>/skills/<name>/ 下，这一层只是指针。\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())