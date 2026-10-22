# 采集观察与报告复核

本流程用于本地候选采集实验。报告计数不等于平台供给总量、有效约稿数或可推送机会数。自动化验收、单次实网和多日持续观察各自记录证据。

## 环境与记录

在项目根目录运行，使用 Python 3.9+、curl、同机本地 SQLite 与 macOS/Linux 文件锁。无需模型或邮件服务。凭证若需要，只通过外部环境变量 `FLN_OAUTH_TOKEN` 注入，不写进命令参数或记录文件。没有凭证时尝试匿名只读访问；历史成功不能保证下一次可用。

长期状态默认在 `data/freelancer.sqlite3`。一次性实验、日志、导出和环境记录放 `temp/`；本工单冒烟使用独立的 `temp/implementation-07/live.sqlite3`，不会混入长期状态。保留旧原型与旧实验不变。

每次实验先记录：Python/curl 与系统版本、状态路径、凭证模式（仅写匿名或环境凭证）、查询词、条数和页数上限、总请求/总秒数上限、单请求超时、复查批量、频率、计划起止或最大次数、实际开始与结束时间（UTC）、进程/设备停止情况。运行报告持久保存实际配置和请求结果；调度状态保存频率、上限及事件。环境信息需另记，报告不会凭空推断机器在线时间。

## 单次运行及抽查

下面是一次有界搜索例子（执行命令会真实请求来源）：

```bash
python3 -m opportunity_intake run --query illustration --query portrait \
  --limit 5 --pages 1 --max-requests 3 --request-timeout 10 \
  --max-seconds 30 --recheck-limit 1
python3 -m opportunity_intake runs
python3 -m opportunity_intake list
python3 -m opportunity_intake ended
```

`runs` 查看每轮开始/结束、请求范围、成功/部分完成/失败/跳过和计数；`list` 直接查看当前保留的候选、来源网址、原始字段、时间和状态；`ended` 仅含最小结束记录。每轮先有限复查已存候选，再搜索；复查和搜索共用总预算。满页、耗时/请求上限或未完成的复查都可能造成截断。退出码 0 也可能是 partial/skipped，应检查报告中的状态。

抽查时查看 `field_status`：`unknown`/`invalid` 不能解释为已确认；预算的 `partial` 也不表示完整披露。`published_at` 与发现/读取时间不同；曾有可靠发布时间但本轮缺失时可保留旧值，最新字段状态仍可为未知。地域未说明不等于确认接受中国画师；未核实/无法核实不等于确认仍可接单。最近成功核验时间仅证明那次观察。

人工抽查结论在独立记录中写明抽查时间、样本选择方式、样本数、相关/不相关/无法判断的数量及依据，不纳入采集数量，不据此新增人工录入工作流。本工单没有执行相关性抽查或自动分类。候选详情按需即时查看，汇总导出不包含项目正文、预算值或项目标识，不创建详情缓存。

## 有限期调度（需要操作者显式执行）

以下为操作示例，本工单没有运行这些实网调度命令。频率/次数是示例参数，不是默认启用或观察天数门槛。

```bash
python3 -m opportunity_intake schedule start --query illustration --query portrait \
  --limit 5 --pages 1 --max-requests 3 --request-timeout 10 --max-seconds 30 \
  --recheck-limit 1 --interval-seconds 3600 --max-runs 3
python3 -m opportunity_intake schedule status
python3 -m opportunity_intake schedule work
```

也可以用显式带时区的未来 `--until` 替代 `--max-runs`，同时提供时先达到任一上限就停止。`start` 只保存计划；`work` 是前台执行器，不安装系统任务。第一轮立即尝试，后续间隔从上一轮结束算起。到期或次数用尽退出；限流尊重来源等待。

```bash
python3 -m opportunity_intake schedule pause
python3 -m opportunity_intake schedule resume
python3 -m opportunity_intake schedule work
python3 -m opportunity_intake schedule stop
```

暂停/停止在另一个终端操作；在途的一轮按预算收尾。暂停会使执行器退出，恢复后需再次显式 `work`。机器停止后不会自动恢复；重启执行器才核对持久进度与观察缺口。实际结束时间和停机情况必须记录，不能把计划时长当作已运行时长。恢复过程中可能因预算用尽结束，无须继续采集才能导出报告。

## 汇总导出

```bash
mkdir -p temp/observation
python3 -m opportunity_intake report \
  --start 2026-10-22T00:00:00+00:00 --end 2026-10-23T00:00:00+00:00 \
  > temp/observation/report.json
```

替换为实际记录的观察范围。所有命令支持 `--state PATH`；`report` 不创建缺失的数据库，不发网络请求。公开 Python 入口：`opportunity_intake.reporting.observation_report(store, start=..., end=..., now=...)`。日期必须有时区且终点晚于起点；转换为 UTC 后按 `[start, end)` 选取开始于该范围的轮次。每日包含零运行日、首尾不满一天的桶；开始在范围内但结束在范围外的轮次，其已保存结果整体归入开始日。历史报告使用导出时已保存的事实，恢复/删除后重新导出可以变化，不是“截至当时”的数据库快照。

- `total` 与 `daily`：状态计数、请求尝试/成功/失败、错误类别与 HTTP 状态、没有保存结果的在途请求、截断轮数、新增/变化观察数、去重候选、近期数、字段覆盖、核验次数、明确结束、结束命中、无效条目及观察缺口。
- `run_diagnostics`：每轮配置、实际搜索查询/偏移/条数、响应结果、跳过原因、待复查数和截断标记。结合计划范围与实际请求确定未读范围；不据此推算未读项目数。
- `schedules`：在报告终点前创建的计划与持久事件（包含旧计划）；这是导出时的计划上下文，可能含范围外的事件。`schedule_events` 只按事件发生时间统计，缺口按与报告范围的交集统计并合并重叠秒数。
- `current_candidates`：导出当下全库保留集合的数量、字段、待整理、状态与曾成功核验数，不限于观察范围。其近期分类按导出时间重算；没有历史详情副本，需用 `list` 即时抽查。

去重身份为来源 + 项目 ID。`unique_new_candidates` 是桶内曾新增的不同身份数；同轮、跨查询和跨轮重复不增加它。`new_observations` 是入库事件数；删除后再发现可能再次计为新入库，不能叫两个唯一项目。`candidate_observations` 是逐轮唯一观察数的和，不能当作跨轮唯一候选数。

字段覆盖与近期分类用桶内每个身份最后一次保留观察，分母为 `unique_observed_candidates`，而非请求数或平台总量。`known_fraction` 仅计算 known，partial 单列；空分母返回 null。历史 `recent_candidates` 表示在该身份最后一轮观察时，来源发布时间落于该轮起点向前 3 天闭区间内；它不表示导出时仍近期。未知/无效时间、未来时间和较旧时间分别处理。

来源删除会清除候选及历史引用，保留必要匿名计数。此时 `unique_counts_complete=false`，`unique_new_candidates=null`，可识别部分以 `identifiable_unique_new_candidates` 和 `unique_observed_candidates` 展示；字段覆盖与近期数仅针对剩余可识别观察。`redacted_candidate_observations` 标注清除量；旧版无逐项证据也计入 `unavailable_candidate_observations`。不为重算唯一数秘密保留已要求删除的标识。既有导出是当时的匿名汇总，不能用它恢复候选详情；重新导出读取实时数据库。

`running` 代表没有持久结束报告，不证明有活进程；`known_interrupted_runs` 用调度恢复事件关联运行开始日。调度 overlap/deferred 等事件不凭空补成完整采集运行；手动锁冲突若没有持久记录无法事后重建。缺口来自保存的调度事件，不代表漏掉多少项目，也不证明设备关机；尚未恢复的调度可能还未写出缺口。零缺口、零失败或全成功均不能证明全天在线。请求终点在未来时 `requested_end_in_future=true`，未来部分没有观察证据。

## 验证层次

1. 自动化：`python3 -m unittest discover -s tests -v`，随后 `temp/implementation-tools/bin/mypy opportunity_intake tests`。来源与时间可控，存储为项目 `temp/` 下真实隔离 SQLite；不依赖实网或等待数日。
2. 单次实网：记录执行时间、环境、配置、响应、保存与报告核对结果；失败也如实记录，不能改写成零供给。一次成功只证明当次读取。
3. 多日观察：操作者选择起止、频率和预算并显式启动，结束后汇总真实运行事实和抽查结论。没有最低项目量、回复量、付费或固定 3–7 天门槛；尚未发生的观察标“未执行”。

本轮具体结果见 [第 07 张验收记录](reviews/ticket-07-observation-report-and-verification.md)。
