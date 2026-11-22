# 修复小米互传自动关闭

拦截 mishare_enabled=false 写入、把 switch_status 抬到 2、屏蔽空白倒计时 Toast。

- 补丁文件：`patch.diff`
- 检测规则：`detect.json`
- 应用顺序：20

## 三段判定

1. `upstream_absorbed_if` 任一命中 → **ABSORBED**，跳过本补丁（以上游实现为准）
2. `our_markers` 全部命中 → **ALREADY_APPLIED**，跳过
3. `git apply --check` 通过 → **APPLIED**；失败 → **FAILED**
