# 第 07 张：观察期报告与实验复核

评审基准：`f8cb8fe`。正式工单：[07](../../.scratch/freelancer-continuous-intake/issues/07-observation-report-and-verification.md)。操作及口径：[runbook](../observation-runbook.md)。

## 已实现

公开 `observation_report` 与 `report --start --end` 命令从同一 SQLite 读取快照生成 UTC 每日及全期匿名汇总。保留单轮配置和实际搜索范围、状态、错误、截断、核验、缺口及恢复上下文；使用全部持久计划而非只看最后一个计划。当前详情由已有 `list` 入口即时提供，报告不复制机会详情。

跨查询/跨轮按来源与 ID 去重，字段覆盖及历史近期数按桶内最后观察计数。来源删除之后，缺少身份的观察量明确标注，精确唯一新增返回 null；入库事件数与可识别唯一数分开，避免删除后再发现虚增唯一项目。当前候选近期数按导出时钟重算。详情结束和来源删除不因生成报告而恢复。

## 自动化验收

- `python3 -m unittest discover -s tests -v`：86 项通过，10.956 秒。
- `temp/implementation-tools/bin/mypy opportunity_intake tests`：18 个源文件严格检查通过。
- `git diff --check`：通过。
- 新增 7 项公开报告验收，驱动完整采集、公开调度、来源删除与真实隔离 SQLite，覆盖跨日重复、内容变化、时间未知、部分失败、结束删除、来源删除、暂停/恢复缺口、旧计划、未结束运行与中断恢复、冷却跳过、CLI、UTC 半开边界和导出时近期变化。
- 报告测试使用替身来源和可控时间；没有把这些测试写成实网或多日运行。

## 本次单次实网

2026-10-22 23:03:23.696652–23:03:23.975779 UTC（本机 America/Los_Angeles 当日 16:03）。macOS/Darwin，Python 3.9.6，curl 8.7.1，匿名模式。隔离数据库 `temp/implementation-07/live.sqlite3`，完整命令见 `temp/implementation-07/smoke-environment.json`。

参数：`illustration`，每页最多 2 条、1 页、最多 1 个请求，单请求 10 秒，总预算 15 秒，复查批量 0。仅一次手动运行，无调度频率、无后台执行器。

结果：1 次搜索成功、0 请求失败，新增 2 个唯一候选，当前保留 2 个，均有已知原始时间并在该轮最近三天内；预算/币种/计价单位有值，地域均未知，状态均未核实。满页达到采样上限，整体 partial、truncated=true。API 适配仅在 HTTP 200、成功信封和项目列表解析通过后记录成功。

原始运行、匿名观察汇总及环境记录分别为 `temp/implementation-07/live-run.json`、`live-observation.json`、`smoke-environment.json`。这些一次性证据仅存 temp，不把来源内容提交到 Git；长期文档只记录必要统计与限制。未检查绘画相关性，未读取详情核验状态，未证明平台总供给或未来匿名可用性。

## 多日证据

**未执行。** 本次没有启动实际多日采集。调度、暂停、恢复和日期推进只在自动化隔离测试中执行；真实冒烟仅上述一次请求。七张工单完成代表实验能力实现，不代表网站/邮件产品完成或多日稳定性已验证。

## 代码评审

待 Standards / Spec 两个独立评审完成后记录结论。
