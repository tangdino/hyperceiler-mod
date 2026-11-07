# HyperCeiler 定制版（patch 架构）

基于上游 [ReChronoRain/HyperCeiler](https://github.com/ReChronoRain/HyperCeiler)（AGPL-3.0）。

## 核心思路：main = 干净上游 + 元文件

本 fork 的 `main` **不包含任何定制源码**。它永远是：

```
上游 main（逐字节一致）
  + patches/          ← 6 项定制的 diff + 吸收检测规则
  + scripts/          ← 补丁调度器
  + .github/          ← 本工作流
  + CUSTOM.md
```

CI 每次运行都是：`reset --hard 上游` → 放回元文件 → 逐个 apply patch → 编译 → 发版。

**好处**：上游改了 `SystemUIB.java` 也**不会产生 git merge 冲突**，只会让某个补丁的
anchor 失效 —— 而 anchor 失效是可精确定位、可按规则判定、可按策略处理的。

## 定制清单

| # | 名称 | 补丁目录 | 内容 |
|---|---|---|---|
| 1 | 移除签名校验提示 | `patches/01-signature-check` | 不弹签名失败横幅；设备信息不采集签名 |
| 2 | 修复小米互传自动关闭 | `patches/02-mishare-autoclose` | 拦 `mishare_enabled=false`；`switch_status` 抬到 2；屏蔽空白 Toast |
| 3 | 隐藏通知省略点 (RmDots) | `patches/03-rmdots` | `IconState#applyToView` 把 `visibleState 1→2` |
| 4 | 桌面监控线程放弃策略 | `patches/04-home-giveup` | 退避 500ms，60s 后停线程，消除单核 28.7% 占用 |
| 5 | 手动检查更新 | `patches/05-manual-update-check` | 点版本卡片查 GitHub release；按 CI runId 比版本；下载后交系统安装器 |
| 6 | versionCode 对齐上游 | `patches/06-versioncode-align-upstream` | versionCode 优先读 CI 注入的 `HC_UPSTREAM_VERSION_CODE`，与上游精确一致 |

另有 `scripts/enforce_infra.py` 处理构建纪律（禁止 debug 签名、`.gitignore`），
不走补丁机制，因为它是「无论上游怎么改都必须成立」的约束。

## 补丁判定：上游优先纪律

`scripts/apply_all.py` 对每个补丁依次判断（核心纪律：**上游的更新代码若与补丁重复，
一律优先采用上游代码**）：

| 判定 | 条件 | 行为 |
|---|---|---|
| `ALREADY_APPLIED` | `our_markers` 全部命中 | 跳过（补丁已在此树中） |
| `ABSORBED` | `detect.json` 的 `upstream_absorbed_if` 任一命中 | **采用上游代码，跳过本补丁** |
| `ABSORBED` | `git apply --reverse --check` 通过（正向失败） | **树里已含相同改动，采用上游代码** |
| `APPLIED` | `git apply --check` 通过 | 应用 |
| `FAILED` | 正反 `git apply` 均失败 | 按 `on_patch_fail` 决定 fail / skip |

`ABSORBED` 就是「上游更新已经包含了我的修改，以上游为准」这条需求的实现方式；
其中 `git apply --reverse` 这条是自动兜底：只要补丁改动已存在于上游源码树，就
无需人工标注 `upstream_absorbed_if` 也会被判为吸收。

## 触发方式

| 方式 | 行为 |
|---|---|
| 定时 `0 6 * * *`（UTC） | 上游有变化才编译+发版 |
| 手动 `force_build` | 无论上游是否变化都编译，产出 artifact，不发版 |
| 手动 `force_release` | 无论上游是否变化都编译 + 推 main + 发版（验证全链路） |
| `on_patch_fail` | `fail`（默认，最安全）/ `skip`（缺功能但能出包） |

## 新增一项定制的步骤

1. 建目录 `patches/NN-name/`
2. 放 `patch.diff`（用 `git diff` 生成，路径相对仓库根）
3. 放 `detect.json`，至少写 `name` / `upstream_absorbed_if` / `our_markers`
4. 无需改 workflow —— `apply_all.py` 自动发现 `patches/*/detect.json`