# Freelancer 详情复查状态依据

核对日期：2026-10-22。仅适用于本地采集实验，不代表可申请资格核验。

[官方 Python SDK 的 get_project_by_id](https://github.com/freelancer/freelancer-sdk-python/blob/master/freelancersdk/resources/projects/projects.py) 使用 `GET /api/projects/0.1/projects/<id>`，成功响应的 `result` 是单个项目对象。适配器请求 `full_description=true`，并要求响应 ID 与所请求 ID 一致；列表结构、错误 ID 或非法对象按复查失败处理。搜索和详情复用同一个有界 HTTP 读取实现。

[官方项目状态说明](https://www.freelancer.com/support/employer/Project/project-status) 说明：Open 是开放投标的当次状态；Closed 可以是未授予项目就关闭，不能理解为已经成交；Complete 表示项目被标记完成。No Freelancer Selected、Awaiting Acceptance 和 In Progress 等状态的含义不同，不能仅凭名称推断招募已经结束。

以下是本适配器对 `frontend_project_status` 的保守映射策略；官方帮助页提供展示状态的语义，大小写敏感的 API 字符串对应关系是实现规则，并非声称官方帮助页列出了完整 API 枚举。

| 精确字段值 | 本地动作 | 原因／说明 |
| --- | --- | --- |
| `closed` | 保存结束记录并清理详情 | `source_closed`；来源明确关闭，不声称成交 |
| `complete` | 保存结束记录并清理详情 | `source_complete`；来源标记完成 |
| `open` | 保留候选，更新成功核验时间 | “来源显示开放，未确认可承接” |
| 缺失或其他值 | 保留候选，标记“无法核实” | 不猜测未知枚举，不刷新成功核验时间 |

`status` 原始字段仍保存为观察信息，不能独立触发删除；404、访问失败、超龄、消失于搜索、高投标数、正在挑选均不触发结束。当前适配器不从自由文本自动判断是否已找到承接者。成功读到但无法解释的状态计入 `rechecks_succeeded` 和 `rechecks_unresolved`，整轮为部分完成；HTTP／解析失败计入 `rechecks_failed`。只有可解释的开放状态更新存活候选的 `last_status_verified_at`；每次尝试记录 `last_status_attempt_at`，失败和含糊状态保留以前的核验时间。

映射由完整运行测试覆盖，另以本机 HTTP 响应验证真实适配器路径、单对象解析和 Complete 结束处理；没有为本工单发起实网项目读取或修改来源项目。
