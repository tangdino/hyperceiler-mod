# 06 · versionCode 对齐上游

## 问题

上游 `app/build.gradle.kts`：

```kotlin
val gitVersionCode: Int by lazy { 5 + gitCommitCount }
```

`gitCommitCount = git rev-list --count HEAD`。

CI 每次同步都会在 main 上多出一个 `sync: upstream xxxxxxx` commit，
于是 fork 产物的 versionCode 恒比上游多 1（实测 **4692 vs 上游 4691**）。

## 改法

```kotlin
val gitVersionCode: Int by lazy {
    System.getenv("HC_UPSTREAM_VERSION_CODE")?.toIntOrNull() ?: (5 + gitCommitCount)
}
```

- CI 注入 `HC_UPSTREAM_VERSION_CODE`（由上游 HEAD 的提交数算出）→ 与上游精确一致
- 本地开发不设该变量 → 行为与上游完全一致，不影响任何人

## 为什么不「直接取 upstream/main 的 count」

浅克隆下 `git rev-list --count` 会失真（实测返回 1），不可靠。
显式注入是唯一稳定做法。

## 副作用

versionCode 与上游相同意味着系统视为「同版本」。
安装同 versionCode 的包需允许降级/重装 —— 本机有核心破解，可覆盖安装。
