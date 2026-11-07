# 桌面监控线程放弃策略

桌面始终找不到 libapp.so 时退避到 500ms，60 秒后永久停止监视线程，消除单核 28.7% 占用。

- 补丁文件：`patch.diff`
- 检测规则：`detect.json`
- 应用顺序：40

## 三段判定

1. `upstream_absorbed_if` 任一命中 → **ABSORBED**，跳过本补丁（以上游实现为准）
2. `our_markers` 全部命中 → **ALREADY_APPLIED**，跳过
3. `git apply --check` 通过 → **APPLIED**；失败 → **FAILED**
