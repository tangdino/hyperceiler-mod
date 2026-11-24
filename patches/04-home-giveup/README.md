# 桌面监控线程放弃策略

桌面始终找不到 libapp.so 时退避到 500ms，60 秒后永久停止监视线程，消除单核 28.7% 占用。

- 补丁文件：`patch.diff`
- 检测规则：`detect.json`
- 应用顺序：40

## 三段判定

1. `upstream_absorbed_if` 任一命中 → **ABSORBED**，跳过本补丁（以上游实现为准）
2. `our_markers` 全部命中 → **ALREADY_APPLIED**，跳过
3. `git apply --check` 通过 → **APPLIED**；失败 → **FAILED**

## 上游已吸收（上游 293cbc08 / 2026-11-05 起）

上游把 `home_layout_engine` 重构为 v2.3，并用 `MonitorPeriodMs(const State&)` 取代了固定
`periodMs = 50`：

- 缺图 / 缺配置 / 稳态 / 卡住一律 `1500 ms`，只有真正需要落补丁时才 `50 ms`；
- 库加载与配置推送通过 `WakeMonitor()` 立即唤醒，不依赖高频轮询。

也就是说本补丁针对的「找不到 libapp.so 时永久 20 Hz 空转、单核 28.7%」问题，上游已自行解决。
按 `CUSTOM.md` 的「上游优先」纪律，`detect.json` 新增两条 `upstream_absorbed_if` 规则，
命中即判 **ABSORBED**，不再应用本补丁（保留 `patch.diff` 作为历史记录：若上游回退该实现，
补丁会自动重新生效）。

因此 2026-10-27 ~ 11-08 连续 13 次 `entry.cpp:43 patch does not apply` 的根因是上游重构导致
anchor 失效，而正确的处置是判定为「上游已吸收」，不是把旧补丁硬套到新代码上。
