# 隐藏通知省略点 (RmDots)

SystemUI NotificationIconContainer$IconState#applyToView 里把 visibleState 1(DOT) 改成 2(HIDDEN)。

- 补丁文件：`patch.diff`
- 检测规则：`detect.json`
- 应用顺序：30

## 三段判定

1. `upstream_absorbed_if` 任一命中 → **ABSORBED**，跳过本补丁（以上游实现为准）
2. `our_markers` 全部命中 → **ALREADY_APPLIED**，跳过
3. `git apply --check` 通过 → **APPLIED**；失败 → **FAILED**
