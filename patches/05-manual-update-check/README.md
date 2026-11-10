# 手动检查更新

点关于页的版本卡片 → 查 GitHub release → 有新版则下载 → 调起系统安装器。

## 为什么用 CI runId 而不是 versionCode

tag 形如 `v2.10.166-r40005741620`，本地 versionName 是 `2.10.166-5b0921ba3-r4692`。
末尾的 4692 是上游 versionCode，与本 fork 的构建序号无关，两者永远比不出大小。
因此 CI 每次把 `github.run_id` 写进 `assets/build_run_id.txt`，App 读它和 tag
里的 runId 做数值比较。读不到就明确报错，绝不拿 GIT_CODE 兜底——那会把
四千级的 versionCode 和千万级的 runId 相比，永远误判「有新版本」。

## 网络两级回退

1. `api.github.com/repos/tangdino/hyperceiler-mod/releases?per_page=5`
   一次拿到 tag / 正文 / assets（文件名、大小、digest），能校验大小与 sha256。
2. API 超限额（匿名 60 次/小时/IP）或被阻断时，退到
   `github.com/.../releases/latest` 的 302 Location 头，只解析 tag。

## 触发方式

仅手动。上游的 `VersionCard.onClick` 原本是空实现（`setUpdateInfo` 全仓零调用者，
上游根本没有自动检查更新），本补丁是从零新增入口。

## 安装

下载到 `cacheDir/updates/update.apk`，经 FileProvider（authority
`<applicationId>.fileprovider`，`file_paths.xml` 已加 `updates/` 缓存路径）
交给系统安装器，用户自己确认安装。需要 REQUEST_INSTALL_PACKAGES 权限。
