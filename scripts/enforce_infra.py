#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础设施改写：禁止 debug 签名 + .gitignore 追加。

这两项不属于「功能定制」，而是 fork 的构建纪律，因此不走 patches/ 的补丁机制，
改用容错的文本改写：上游即使改了这一段，只要还能找到 fallback 表达式就能改成功。

注意（踩坑记录）：替换文本里绝对不能出现反斜杠转义序列（如 \\n）。
Python 源码 -> Python 字符串 -> Kotlin 源码，要过三层转义，任一层少转一次
就会把 \n 变成真换行，导致 Kotlin 报 "Expecting '\"'"。因此异常消息写成
纯单行、无 + 拼接、无转义符。

用法：enforce_infra.py --repo <源码根> [--dry-run]
退出码：0 成功；3 找不到目标锚点（上游结构变了，需人工确认）
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

GRADLE = "app/build.gradle.kts"
GITIGNORE = ".gitignore"

# 上游原文：val signingConfigName = if (properties != null) "hasProperties" else "debug"
FALLBACK_RE = re.compile(
    r'val\s+signingConfigName\s*=\s*if\s*\(\s*properties\s*!=\s*null\s*\)\s*"hasProperties"\s*else\s*"debug"'
)

MSG = (
    "缺少 signing.properties：本项目禁止 debug 签名。"
    "请在工程根目录创建 signing.properties，"
    "至少包含 storeFile / storePassword / keyAlias / keyPassword / gpr.user / gpr.key"
)

# 单行，无换行转义，无字符串拼接 —— 规避多层转义陷阱
REPLACEMENT = (
    'val signingConfigName = if (properties != null) "hasProperties"\n'
    '                else throw GradleException("' + MSG + '")\n'
)

# 已经改好的特征（幂等判断）
ALREADY_MARK = "本项目禁止 debug 签名"

# .gitignore 必须包含的条目
GITIGNORE_NEEDED = [
    "signing.properties",
    "hyperceiler-release.keystore",
    "*.keystore",
    "*.jks",
]


def patch_gradle(gradle: Path, dry_run: bool) -> tuple[bool, str]:
    text = gradle.read_text(encoding="utf-8")

    if ALREADY_MARK in text:
        return True, "禁止 debug 签名已生效，跳过"

    new_text, n = FALLBACK_RE.subn(REPLACEMENT, text, count=1)
    if n == 0:
        return False, (
            "找不到 fallback 表达式，期望锚点：\n"
            '  val signingConfigName = if (properties != null) "hasProperties" else "debug"\n'
            "上游可能重写了签名配置逻辑，需人工确认是否还有 debug 回退。"
        )

    if not dry_run:
        gradle.write_text(new_text, encoding="utf-8")
    return True, "禁止 debug 签名：已从 debug 回退改为抛异常"


def patch_gitignore(gi: Path, dry_run: bool) -> tuple[bool, str]:
    if not gi.is_file():
        if not dry_run:
            gi.write_text("# 构建机密，禁止入库\n" + "\n".join(GITIGNORE_NEEDED) + "\n"
                          + "\n# 本地备份文件\n*.bak-*\n", encoding="utf-8")
        return True, ".gitignore 不存在，已新建"

    text = gi.read_text(encoding="utf-8")
    lines = {ln.strip() for ln in text.splitlines()}
    missing = [x for x in GITIGNORE_NEEDED if x not in lines]

    if "*.bak-*" not in lines:
        missing.append("*.bak-*")

    if not missing:
        return True, ".gitignore 已齐备，跳过"

    if not dry_run:
        body = text.rstrip("\n") + "\n\n# 构建机密 / 本地备份，禁止入库\n"
        body += "\n".join(missing) + "\n"
        gi.write_text(body, encoding="utf-8")
    return True, ".gitignore 已追加：" + ", ".join(missing)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    gradle = repo / GRADLE

    if not gradle.is_file():
        print("::error::找不到 %s" % GRADLE, file=sys.stderr)
        return 3

    ok, msg = patch_gradle(gradle, args.dry_run)
    print("[INFRA   ] %s" % msg)
    if not ok:
        print("::error::%s\n%s" % (GRADLE, msg), file=sys.stderr)
        return 3

    ok, msg = patch_gitignore(repo / GITIGNORE, args.dry_run)
    print("[INFRA   ] %s" % msg)

    # 自检：改完后 Gradle 文件里不允许出现裸换行夹在字符串里（粗查未闭合引号）
    if not args.dry_run:
        after = gradle.read_text(encoding="utf-8")
        for i, ln in enumerate(after.splitlines(), 1):
            q = ln.count('"') - ln.count('\\"')
            if q % 2 != 0:
                print("::error::%s:%d 引号未闭合：%s" % (GRADLE, i, ln.strip()),
                      file=sys.stderr)
                return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
