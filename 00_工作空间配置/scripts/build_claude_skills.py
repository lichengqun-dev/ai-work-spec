#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 .claude/skills/ 挂载层（官方格式：每个 skill 是一个**完整目录**）

## 为什么需要这一层

知识库里的 Skill 定义分散在 `<域>/skills/<name>/` 下，而 Claude 的 skill 发现机制只认
`.claude/skills/<name>/SKILL.md` 这类位置。没有这一层，使用者必须知道路径、手动让 AI 去读，
这正是不好上手的原因。

## 为什么现在是「整目录复制」，而不是「只放一个 SKILL.md」

官方格式（Anthropic Agent Skills）里，`SKILL.md` 用**相对 skill 目录**的路径引用
`references/` `scripts/` `assets/`。早期实现只在挂载目录里放一个 `SKILL.md`，里面写的是
"知识库根相对路径"——那在挂载位置是一张**指路牌**，不是 skill：
在它自己那个位置读 `references/INDEX.md` 会直接断。

所以挂载层必须让这些子目录**在挂载位置可见**。

## 两种模式

| 模式 | 做法 | 代价 |
|---|---|---|
| 默认 | **整目录复制** | 有副本，靠 `--check` 保证不分叉；任何平台可用 |
| `--symlink` | 建立**符号链接** | 唯一真实定义，无副本；要求平台支持 symlink（Windows 检出需开发者模式） |

用法：
  python3 00_工作空间配置/scripts/build_claude_skills.py            # 生成/更新（复制）
  python3 00_工作空间配置/scripts/build_claude_skills.py --symlink  # 生成/更新（符号链接）
  python3 00_工作空间配置/scripts/build_claude_skills.py --check    # 只校验是否同步

退出码：0 成功或已同步 ｜ 1 不同步（--check）｜ 2 脚本自身错误
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("错误：缺少 PyYAML。安装：pip install pyyaml\n")
    sys.exit(2)

# 挂载层不该携带的噪音（源码目录里可能有）
IGNORE = ("__pycache__", ".DS_Store", ".gitignore", "*.pyc")


def find_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "CLAUDE.md").is_file() and (p / "09_资产库").is_dir():
            return p
    raise SystemExit("未找到仓库根目录")


def read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise SystemExit(f"{path}：缺少 frontmatter（官方格式要求 SKILL.md 以 --- 开头）")
    fm = text.split("---")[1]
    return yaml.safe_load(fm) or {}


def collect(root: Path):
    """找出全部顶层 Skill（排除 projects/——项目级 Skill 不参与挂载）。"""
    out = []
    for p in sorted(root.rglob("SKILL.md")):
        parts = p.relative_to(root).parts
        if parts[0] in (".git", ".claude", "projects"):
            continue
        meta = read_frontmatter(p)
        name, desc = meta.get("name"), meta.get("description")
        if not name or not desc:
            print(f"  ⚠️ {p}：缺 name 或 description，跳过（它是 skill 发现的前提）")
            continue
        if name != p.parent.name:
            print(f"  ⚠️ {p}：name={name} 与目录名 {p.parent.name} 不一致，跳过")
            continue
        out.append((name, str(desc), p.parent))
    return out


def tree_files(d: Path) -> dict[str, str]:
    """目录内全部文件的内容指纹（相对路径 → 短哈希）。"""
    out: dict[str, str] = {}
    for p in sorted(d.rglob("*")):
        if not p.is_file() or p.is_symlink():
            continue
        rel = p.relative_to(d)
        if any(part == "__pycache__" or part.startswith(".") for part in rel.parts):
            continue
        out[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    return out


def make_symlink(src: Path, dst: Path) -> None:
    import os
    rel = os.path.relpath(src, dst.parent)
    dst.symlink_to(rel, target_is_directory=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 .claude/skills/ 挂载层")
    ap.add_argument("--check", action="store_true", help="只校验是否与真实定义同步")
    ap.add_argument("--symlink", action="store_true",
                    help="用符号链接替代整目录复制（唯一真实定义，无副本）")
    ap.add_argument("--repo", help="仓库根目录")
    args = ap.parse_args()

    root = Path(args.repo).resolve() if args.repo else find_root(Path(__file__).resolve())
    skills = collect(root)
    out_dir = root / ".claude" / "skills"

    if args.check:
        problems: list[str] = []
        for name, _desc, src in skills:
            dst = out_dir / name
            if not dst.exists():
                problems.append(f"{name}：挂载层缺失（不会被 skill 发现机制看到）")
                continue
            if dst.is_symlink():
                if dst.resolve() != src.resolve():
                    problems.append(f"{name}：符号链接指向 {dst.resolve()}，应为 {src}")
                continue
            a, b = tree_files(src), tree_files(dst)
            for rel in sorted(set(a) - set(b)):
                problems.append(f"{name}：挂载层缺 {rel}")
            for rel in sorted(set(b) - set(a)):
                problems.append(f"{name}：挂载层多出 {rel}（真实定义里没有）")
            for rel in sorted(set(a) & set(b)):
                if a[rel] != b[rel]:
                    problems.append(f"{name}：{rel} 与真实定义不一致")
        existing = {d.name for d in out_dir.iterdir()} if out_dir.is_dir() else set()
        for stale in sorted(existing - {n for n, _, _ in skills}):
            problems.append(f"{stale}：挂载层存在但知识库里已无此 Skill")
        if problems:
            print(f"\n❌ 挂载层与真实定义不同步（{len(problems)} 处）：")
            for x in problems[:20]:
                print(f"   {x}")
            if len(problems) > 20:
                print(f"   …还有 {len(problems) - 20} 处")
            print("\n   修复：重建挂载层（ai-spec-mount），或加 --symlink 换用符号链接\n")
            return 1
        print(f"\n✅ 挂载层与真实定义一致（{len(skills)} 个 Skill）\n")
        return 0

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    for name, _desc, src in skills:
        dst = out_dir / name
        if args.symlink:
            make_symlink(src, dst)
        else:
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*IGNORE))
    mode = "符号链接" if args.symlink else "整目录复制"
    print(f"\n✅ 已挂载 {len(skills)} 个 Skill 到 .claude/skills/（{mode}）")
    if not args.symlink:
        print("   每个挂载目录都含 SKILL.md + references/ + scripts/ + assets/，")
        print("   所以 SKILL.md 里的相对路径在挂载位置同样可解析。")
        print("   副本与真实定义的一致性由 --check 保证。\n")
    else:
        print("   真实定义只有一份（知识库里的 <域>/skills/<name>/）。\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())