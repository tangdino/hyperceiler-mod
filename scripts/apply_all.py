#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HyperCeiler 定制补丁调度器。

在「干净上游源码树」上逐个应用 patches/*/patch.diff，并做三段判定：

  1. ABSORBED        upstream_absorbed_if 任一命中 → 上游已自行实现，跳过本补丁
  2. ALREADY_APPLIED our_markers 全部命中        → 补丁已在树里，跳过
  3. APPLIED         git apply --check 通过后实际应用
  4. FAILED          git apply 失败 → 按 --on-fail 决定 fail / skip

用法：
  apply_all.py --repo <源码根> [--on-fail fail|skip] [--dry-run] [--json-out <path>]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ABSORBED = "ABSORBED"
ALREADY = "ALREADY_APPLIED"
APPLIED = "APPLIED"
FAILED = "FAILED"
SKIPPED = "SKIPPED"


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None
    except OSError:
        return None


def rule_hit(repo: Path, rule: dict) -> bool:
    """单条规则是否命中。支持 exists / contains / absent_contains 三种谓词。"""
    target = repo / rule["path"]
    text = read_text(target)

    if rule.get("exists") is True:
        return target.exists()
    if rule.get("exists") is False:
        return not target.exists()

    if "contains" in rule:
        return text is not None and rule["contains"] in text
    if "absent_contains" in rule:
        # 文件不存在时视为「不含」= 命中（上游可能整个删掉了）
        return text is None or rule["absent_contains"] not in text

    raise SystemExit("detect.json 里有无法识别的规则: %r" % (rule,))


def any_hit(repo: Path, rules: list[dict]) -> tuple[bool, str]:
    for rule in rules or []:
        if rule_hit(repo, rule):
            return True, json.dumps(rule, ensure_ascii=False)
    return False, ""


def all_hit(repo: Path, rules: list[dict]) -> bool:
    return bool(rules) and all(rule_hit(repo, r) for r in rules)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


def apply_patch(repo: Path, patch: Path, dry_run: bool) -> tuple[bool, str]:
    """先 check 再 apply。返回 (成功, 错误信息)。"""
    check = git(repo, "apply", "--check", "--whitespace=nowarn", str(patch))
    if check.returncode != 0:
        return False, (check.stderr or check.stdout).strip()
    if dry_run:
        return True, ""
    real = git(repo, "apply", "--whitespace=nowarn", str(patch))
    if real.returncode != 0:
        return False, (real.stderr or real.stdout).strip()
    return True, ""


def discover(repo: Path) -> list[Path]:
    return sorted(repo.glob("patches/*/detect.json"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="源码根目录")
    ap.add_argument("--on-fail", default="fail", choices=["fail", "skip"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / "patches").is_dir():
        print("::error::%s 下找不到 patches/" % repo, file=sys.stderr)
        return 1

    results = []
    failed = []

    for detect_path in discover(repo):
        cfg = json.loads(detect_path.read_text(encoding="utf-8"))
        name = cfg.get("name", detect_path.parent.name)
        patch = detect_path.parent / "patch.diff"

        entry = {"id": detect_path.parent.name, "name": name, "status": SKIPPED, "detail": ""}

        # 1. 已经打过了？
        # 必须排在 ABSORBED 之前。absorbed 规则多为「上游特征不存在」的否定式，
        # 而我们的补丁正是删除该特征，所以补丁一应用，「上游未实现」就成立，
        # 会被误判成 ABSORBED。先认自己的标记才符合语义。
        if all_hit(repo, cfg.get("our_markers", [])):
            entry["status"] = ALREADY
            entry["detail"] = "our_markers 全部命中"
            results.append(entry)
            print("[ALREADY ] %s —— 补丁已在源码树中" % name)
            continue

        # 2. 上游已实现？
        hit, why = any_hit(repo, cfg.get("upstream_absorbed_if", []))
        if hit:
            entry["status"] = ABSORBED
            entry["detail"] = "上游已实现，采用上游版本：%s" % why
            results.append(entry)
            print("[ABSORBED] %s —— 上游已实现，跳过" % name)
            continue

        if not patch.is_file():
            entry["status"] = FAILED
            entry["detail"] = "缺少 patch.diff"
            failed.append(entry)
            results.append(entry)
            print("[FAILED  ] %s —— 缺少 %s" % (name, patch), file=sys.stderr)
            continue

        # 3. 应用
        ok, err = apply_patch(repo, patch.resolve(), args.dry_run)
        if ok:
            entry["status"] = APPLIED
            entry["detail"] = "dry-run" if args.dry_run else ""
            results.append(entry)
            print("[APPLIED ] %s%s" % (name, " (dry-run)" if args.dry_run else ""))
        else:
            entry["status"] = FAILED
            entry["detail"] = err
            results.append(entry)
            failed.append(entry)
            print("[FAILED  ] %s\n%s" % (name, err), file=sys.stderr)

    # 汇总
    summary = {k: sum(1 for r in results if r["status"] == k)
               for k in (APPLIED, ALREADY, ABSORBED, FAILED, SKIPPED)}
    print("\n汇总: " + "  ".join("%s=%d" % (k, v) for k, v in summary.items() if v))

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps({"summary": summary, "patches": results}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    # 写 GitHub Actions step summary（存在才写）
    step_summary = Path("/tmp/hc-patch-summary.md")
    lines = ["| 补丁 | 状态 | 说明 |", "|---|---|---|"]
    for r in results:
        lines.append("| %s | `%s` | %s |" % (r["name"], r["status"],
                                              (r["detail"] or "").replace("\n", " ")[:120]))
    step_summary.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if failed and args.on_fail == "fail":
        print("::error::%d 个补丁应用失败且 on-fail=fail，终止构建" % len(failed), file=sys.stderr)
        return 2
    if failed:
        print("::warning::%d 个补丁应用失败，按 on-fail=skip 继续" % len(failed), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
