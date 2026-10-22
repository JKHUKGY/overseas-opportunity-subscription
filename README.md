# 海外绘画约稿机会采集实验

当前实现：工单 01–06，手动读取 Freelancer 候选、持久保存和去重，识别内容变化与近期候选，轮转复查已存项目，排除确认结束的机会，支持来源删除及有界定时执行，并在失败、限流或进程中断时保全已完成进度。运行依赖 macOS／Linux、Python 3.9+ 和 curl（进程锁使用本地文件系统的 flock）；运行时无需安装 Python 第三方包。

## 使用

从项目根目录运行：

```bash
python3 -m opportunity_intake run
python3 -m opportunity_intake list
python3 -m opportunity_intake runs
python3 -m opportunity_intake ended
```

每次 `run` 执行一轮并退出。默认先复查最多一个已存候选，再查询 illustration 和 portrait，每组一页、最多五条；全轮最多两个请求，每个请求最多 20 秒，来源读取窗口最多 40 秒。详情与搜索共享预算，因此已有候选时，默认预算可能只够一次复查和一个关键词搜索。需要一次复查加两个搜索时设 `--max-requests 3`。可显式调整：

```bash
python3 -m opportunity_intake run --query illustration --limit 2 --max-requests 1 --request-timeout 10 --max-seconds 12
```

`--recheck-limit` 控制每轮最多复查多少个已存候选（默认 1，设为 0 暂停详情复查）；`--query` 可重复提供；`--pages` 控制每个关键词最多读取多少页，所有查询共享 `--max-requests` 预算。单页不足设定条数时停止该词的分页。页数或请求预算限制了进一步读取时，报告会明确 `truncated: true`，不会将样本说成平台全量。

数据默认存入项目的 `data/freelancer.sqlite3`，不进入 Git。`run`、`list`、`runs`、`ended`、`delete-source` 都可用 `--state` 指定另一份持久状态；查看命令要求该状态已经存在。测试与一次性验证文件使用项目 `temp/`。

需要凭证时从 `FLN_OAUTH_TOKEN` 环境变量读取，CLI 不提供令牌参数。传给 curl 时使用标准输入，不写入命令行、状态和运行报告；HTTP 错误只保留类型与状态码，不保存原始错误响应或需求方账户对象。正常情况下可先使用未配置令牌的有界只读运行，是否允许访问以实际结果为准。

## 保存内容与结果含义

候选包含来源和稳定 ID、原网址与规范化网址、标题、来源返回的当前需求正文、原始发布时间、首次发现和最近读取时间、原币种预算与计价方式、来源状态、待整理状态。没有可靠值的字段保持未知；暂不读取附件、图片或评论，也不生成 AI 中文摘要。

“必要正文”在本工单中具体使用来源返回的 `description`，缺失时使用 `preview_description`；不会下载完整网页、附件或扩展需求方资料。最近成功状态核验时间只由可明确解释的详情状态更新；搜索和无法核实的响应不会伪造这一时间。地域资格标记为“地域未说明”，未作申请资格核验。

相同来源及 ID 更新同一候选，保留首次发现时间。搜索保留已有接单状态和核验时间；详情复查可以更新状态。整理输入未变时保留已有处理状态；输入变化时使旧整理结果失效。每次成功请求的候选与运行进度在同一个 SQLite 事务内提交；某一批写入失败只回滚该批，不清空此前成功保存的数据。旧版本数据库会自动从 schema 1／2／3 升到 4，保留候选及报告；无法识别或损坏的状态会明确报错。

报告中 `received_count` 是实际返回条目数（每次成功详情读取计一条），`unique_count` 是本轮实际保存的有效候选的不同 ID 数，`new_count` 是新入库数，`duplicate_count` 是有效条目中已存在或同轮重复的次数，`invalid_count` 是本轮处理范围内身份无效的记录数。确认结束的详情以及命中结束记录的搜索条目不进入候选新增／变化／未变化统计。达到配置条数后的额外响应不入库。未知字段不等于无效身份；这些数量均不代表已经确认的约稿机会数。

### 内容版本与近期统计

`content_version` 从 1 开始。标题、正文、原币种预算上下限、币种、计价方式或地域字段有变化时递增；恢复成更早内容也算一次新变化。内容没有变化时保留版本和已有的 `classification`、`summary`、`processing_status`；变化时清空前两项，并把处理状态设为 `pending`。这里只维护失效状态，不调用模型，也没有新增人工录入功能。发布时间、读取时间及来源状态的变化单独保存，不作为这一阶段的内容版本输入。

本轮去重后的候选分为 `new_count`、`changed_count` 和 `unchanged_count`，三项之和等于 `unique_count`。每个来源及 ID 只计一次：本轮新增优先归入新增；本轮开始前已存在且任一次观察发生内容变化的归入变化；其余归入未变化。`duplicate_count` 仍保留原有按条目统计的含义，不能与这三项相加作为候选总数。

候选的 `last_change` 表示它最近参与的采集运行中的类别，`last_read_at` 表示最近一次读取。报告的 `candidate_results` 只保存来源、ID、变化类别、时间范围状态和字段状态，不保存正文、摘要或预算值。该列表按项目去重；同轮多次观察时，字段与时间状态采用最后一次成功保存的观察值。

最近三天采用 UTC 下的闭区间 `[运行开始时刻 − 72 小时, 运行开始时刻]`，整轮共用同一窗口。`recent_count` 只计算本轮实际读取、原始发布时间已知且落在该窗口内的不同候选；不统计未重读的历史候选，不外推平台全量。报告明确记录 `recent_window_start`、`recent_window_end` 与 `statistics_timezone`。候选中的 `recency` 为 `recent`、`older`、`future` 或 `unknown`，`recency_as_of` 表示判断时刻；查看历史候选时应同时看这个时刻，它不会随打开列表自动刷新。

来源时间使用 `time_submitted`，缺失时使用 `submitdate`，只接受可解析的数值 Unix 秒数。合法的来源修正值更新 `published_at`，并用 `published_at_read_at` 记录取得这个值的时刻，不会重写首次发现时间或冒充成功状态核验。后续响应缺失时间、给出非数值、非有限数或超出可解析范围时，保留此前最后一次可靠的 `published_at` 及其读取时刻；从未取得可靠值时才保持为空，绝不以运行时间补齐。旧候选没有记录这个读取时刻时保持为空，不追溯编造。

`field_status.published_at`、`recency` 和近期计数反映本轮最后一次观察：本次响应没有可靠时间时，即使保留了以前的可靠值，也标记为未知／无效并排除本轮近期计数。这样既保全来源历史可靠值，也不把缺失响应说成已完成时间确认。未来时间单列为 `future`，不计入近期候选。

`field_status` 和报告的 `field_counts` 显示发布时间、标题、正文、预算、币种、计价方式及地域的字段状态。统计分母均为本轮 `unique_count`；未出现的状态计数视为 0。预算按 `known`、`partial`、`unknown`、`invalid` 区分，负数、非有限数与倒置区间不作为有效预算；有效的单边预算可保留。固定总价与时薪分别保留为 `fixed`、`hourly`，未知单位保持为空。不拿投标均价补预算，不生成汇率换算；地域始终保持“地域未说明”。字段不足不等于候选身份无效。

旧候选在下一次成功读取时补齐这些字段；未记录版本的候选以原有内容作为版本 1 的比较基准。未重读的旧候选和旧运行报告可能没有新字段。内容版本是当前状态标识，数据库不新增历史正文副本。

`requests` 按实际请求顺序记录 `kind: search/detail`、成功／失败及返回条数；搜索带关键词、偏移量和请求条数，详情带来源与项目 ID；失败时附错误类型和可用的 HTTP 状态。由此可以区分“计划查询但因预算没有执行”和“确实执行后返回零条”。运行历史不包含来源正文或凭证。较早版本的实网验证报告可能没有该字段。

运行结果如下：

| 状态 | 含义 |
| --- | --- |
| `success` | 计划范围正常完成，允许零条结果 |
| `partial` | 达到分页／条数／请求或时间上限、仍有待复查候选、存在坏记录／无法核实的状态，或部分请求失败 |
| `failed` | 来源请求全部失败 |
| `skipped` | 尚在来源等待期，本轮没有访问来源 |
| `running` | 已保存启动或进度记录，但尚无结束记录 |

单次 `run` 对成功／部分完成／跳过返回 0，来源失败返回 1，配置或存储错误返回 2。调用方应同时检查 JSON 状态及 `truncated`。搜索和详情请求共用总请求预算和来源读取窗口，每次超时取配置与剩余窗口的较小值；窗口用尽后不再发起请求。最后的本地持久化仍会完成，因此命令的总墙钟时间可能长于来源读取窗口。

运行开始及每次请求发出前都会保存进度；进程意外退出后，已完成批次仍然可读。下次运行的 `unfinished_run_ids` 列出没有结束记录的历史运行。这些记录可能属于意外中断，也可能属于另一个仍在执行的进程。现在同一状态文件的完整采集和来源删除共用进程锁；手动采集发生重叠时返回未写入数据库的 `skipped / state_busy`，不改写正在进行的运行。恢复时重新读取来源，通过稳定 ID 去重，不假定失败页已经完成。

所有来源错误都会停止本轮后续请求并保留成功批次，401／403 不自动重试。错误报告区分 HTTP 状态、`timeout`、`transport_error`、`transport_unavailable`、`invalid_json`、`invalid_response` 和 `api_error`；单条坏记录计入 `invalid_count`，有效记录继续保存。

429 优先采用 [HTTP Retry-After](https://www.rfc-editor.org/rfc/rfc9110.html#name-retry-after) 的秒数或 HTTP 日期，写入 `next_allowed_at`。缺失或无效时从 60 秒开始翻倍，最高 3600 秒；来源请求成功完成且没有请求失败时重置退避。等待时间与限流次数持久保存，重启后仍有效；未到期的完整运行记为 `skipped`，附 `skip_reason: source_cooldown`，到期后可再运行。程序不在等待期内睡眠重试，也不把原始等待响应、正文或凭证写入报告。

### 复查与结束记录

复查范围取本轮开始时已存的候选，按稳定 ID 轮转；来源即使不再在搜索结果中返回它，也会被复查。每次实际尝试后持久保存游标，失败的候选不会一直占据队首；重启后继续轮转。新发现项目从下一轮开始进入复查范围。请求失败仍停止本轮后续来源访问，下一轮再继续。

详情使用与搜索相同的字段和内容版本规则。`frontend_project_status: open` 标注“来源显示开放，未确认可承接”，记录 `last_status_verified_at`。未知、缺失或其他未映射状态标注“无法核实”，保留以前的成功核验时间，另记 `last_status_attempt_at`。404、网络错误、大量投标、挑选中、搜索消失或发布时间较早均不触发删除。

只有详情的 `frontend_project_status` 明确为 `closed` 或 `complete` 时结束，原因分别为 `source_closed`、`source_complete`；Closed 不代表已成交。具体来源依据及保守映射见[状态映射说明](docs/freelancer-status-mapping.md)。本次用可控响应验证映射，尚未实网核验详情端点返回的状态枚举；未知枚举会保留候选。

结束处理先独立提交最小记录（来源、稳定 ID、原网址、删除时间、原因），再删除候选详情。`deleted_at` 表示结束记录生效、候选停止对外展示的时刻；物理清理在后续事务完成。写入结束记录失败则保留详情；写入后意外退出，`list` 立即隐藏该项目，下次 `run` 先补完删除。结束记录长期保留，重复处理不重复创建。后续读取缺少网址时保留已有原帖网址，避免结束时失去网址排除依据。按来源及稳定 ID，或规范化网址排除再次出现的项目；网址仅移除片段及 `utm_*` 参数，保留其他可能影响身份的参数。

当前应用仅在 SQLite 候选表中维护详情，没有额外详情副本或导出缓存；删除同步清除该记录中的正文、摘要、分类等内容。结束表只另存用于匹配的网址索引，不留正文。运行报告和日志不留正文、摘要或预算值。用户自行重定向的 CLI 输出和历史独立原型不属于当前采集器维护的缓存。

报告区分 `rechecks_attempted`、`rechecks_succeeded`、`rechecks_failed`（读取成功不等于状态已核实）；`rechecks_unresolved` 包含失败和未知状态。`confirmed_ended_count` 统计新写入的结束记录；`ended_record_hits` 统计被排除的出现次数；`recovered_deletions` 统计启动时补完的详情删除数。`pending_recheck_count` 是仍存候选中本轮尚未尝试复查的数量，包括本轮新发现的项目；未核实但已尝试的项目记入 unresolved。启用复查而仍有待复查项时，本轮标注截断；设 0 暂停复查时仍报告待查数量。

### 按来源删除要求清理

收到平台或原作者的明确删除要求后，使用独立的 `delete-source` 命令。每次指定来源以及项目 ID 或原帖网址（二选一）；命令只操作本地现有状态，不访问或联系来源。

```bash
python3 -m opportunity_intake delete-source --source Freelancer --project-id 123456
# 或按原帖网址定位；含查询参数时用引号包住整条网址
python3 -m opportunity_intake delete-source --source Freelancer --url 'https://www.freelancer.com/projects/illustration/example?utm_source=link'
```

公开 Python 入口为 `store.delete_source_data("Freelancer", project_id="123456")`，或以 `url=` 替代 `project_id=`。来源名称和稳定 ID 精确匹配；网址使用与采集相同的规范化规则，只移除片段和 `utm_*` 参数，保留其他身份参数。找到项目后沿同来源的已知 ID／规范网址关联，清理对应候选和结束记录（包括结束后尚未补完物理删除的候选）。不同来源和身份参数不同的独立项目不受影响。

所有清理在一个 SQLite 事务里完成，包括候选正文、摘要、分类等字段、完整结束记录及其网址索引、指向目标项目的复查游标。当前没有其他应用维护的详情副本或导出缓存。没有新增永久屏蔽名单；删除成功后再次采集到该项目，允许作为新候选入库。普通需求结束仍走第 04 张工单的流程，保留最小结束记录。

历史运行报告中目标项目的 `candidate_results` 和详情 `requests` 逐项引用一并移除，分别增加 `redacted_candidate_results` 和 `redacted_detail_requests` 计数。原运行的新增、请求、字段覆盖等汇总保留实际历史值，因此清理后的逐项列表可能少于原汇总，不能再仅靠剩余列表重算原报告。这些报告不保留项目正文、预算值或网址；不新建含删除目标身份的审计副本。来源级等待时间和不相关项目的复查进度不变。

成功结果仅返回 `status: complete` 及 `candidates_deleted`、`ended_records_deleted`、`history_entries_redacted`、`recheck_cursors_deleted` 四个数量，不返回被删除内容或网址。未找到目标或重复删除是成功的零变更。CLI 成功返回 0，参数／存储错误返回 2。状态文件不存在时明确报错，不新建空库冒充删除成功。

中途写入失败时整笔回滚并报错；进程在提交前退出，重开数据库恢复原状态后可以重试；提交后退出但没收到结果，也可以重复调用并通过 `list`／`ended` 核对。不自动提交未完成的删除请求。来源删除与完整采集共用进程锁，忙碌时返回错误，可稍后重试；需要阻止定时采集马上重新发现目标时，先暂停计划并等待当前轮次结束。本命令不清理用户另存的输出、备份或独立历史原型，也不承诺底层介质的取证擦除。

### 有界定时运行

`schedule start` 仅创建持久计划，不发起请求或后台任务。必须显式提供间隔（至少 1 秒）、每轮请求和耗时预算，以及最大次数或带时区的观察终点；两种上限同时提供时先到者生效。以下仅为命令示例，实际参数由运营者选择：

```bash
python3 -m opportunity_intake schedule start --interval-seconds 3600 --max-runs 3 --max-requests 3 --max-seconds 40
python3 -m opportunity_intake schedule status
# 显式启动前台执行器，按持久计划执行至暂停、停止或上限
python3 -m opportunity_intake schedule work
```

各命令均支持 `--state`。`start` 可创建新状态文件；其余操作要求现有状态。可用 `--until '2026-11-01T00:00:00+00:00'` 设置观察终点，也可与 `--max-runs` 同时使用。搜索、分页、详情复查和每次请求超时参数与 `run` 一致。默认 `run` 仍只执行一次。

前台执行器运行期间，可在另一终端控制计划：

```bash
python3 -m opportunity_intake schedule pause
python3 -m opportunity_intake schedule resume
python3 -m opportunity_intake schedule stop
```

暂停和停止不强行终止已认领的一轮，该轮按预算收尾；控制状态不会被收尾覆盖。执行器在暂停时退出，`resume` 只恢复计划状态，之后再次显式运行 `schedule work`。停止或完成的计划不能恢复；需显式新建计划才会获得新的观察次数。若仍有遗留的在途轮次，先用 `schedule tick` 核对恢复后再新建计划。

`schedule tick` 检查并最多执行一轮：未到期返回 `not_due`，等待来源返回 `deferred`，执行后返回 `ran`，重叠返回 `overlap`，非活动计划返回其状态。`work` 在等待期间每秒检查控制状态；遇重叠会退出，计划和进度保留，可在现有操作结束后重新启动。执行器绑定启动时的计划 ID；旧计划被停止并另建新计划时，返回 `schedule_changed`，不会自动执行新计划。Ctrl-C 退出执行器并返回 130，保留计划与已存进度；它不会悄悄把计划重置或启动替代后台任务。

公开 Python 入口是 `Scheduler(store, now=..., clock=...)`，提供 `start(config, interval_seconds=..., max_runs=... / until=...)`、`status()`、`control("pause" / "resume" / "stop")`、`tick(source)` 和 `work(source, wait=...)`。调度直接调用已有 `collect`；测试替换时间、等待与来源，不替换业务实现。

时间统一为 UTC。第一轮在执行器启动且条件满足时运行，后续间隔从上一轮实际结束时刻计算；来源等待时间更晚时推迟到那个时间。请求窗口收紧到观察终点的剩余时间，到期不再开始来源读取，本地保存仍可收尾。限流推迟和重叠跳过不消耗次数。

状态中的 `runs_started` 是已持久认领的尝试数，包含中断尝试；`completed_runs` 是已写成结束报告的轮数，失败报告也算完成一轮。认领后、请求前中断时保守保留该次计数，以免反复重启绕过上限。`inflight_run_id` 指向尚待核对的运行；`last_run_id`／`last_result`、`next_run_at`、`until` 显示最近结果、计划时刻和观察终点。非 active 状态不会因为保留了 next_run_at 而自动执行。

同一数据库的调度触发共用一个进程锁，完整采集和来源删除共用另一个；进程退出后操作系统自动释放锁。数据库旁的两个空 `.lock` 文件可以保留，它们的存在不代表任务仍在运行，不应在执行期间删除。该实现面向同机本地存储，没有配置系统开机自启、云部署或分布式调度。

重启后先核对在途运行：若结束报告已写成，补记调度完成且不重跑；若未写成，事件记为 `interrupted_run`，保留原采集报告缺少结束记录的事实，并在剩余次数和时间允许时继续。因而历史报告的 running 标记不证明当前还有活进程，应结合调度恢复事件查看。

`events` 保留认领、控制操作、重叠、来源等待、恢复完成和中断信息。到期后迟到至少一个完整间隔才触发时，先记录从原到期时间到实际触发时间的 `observation_gap`，再处理可能的限流推迟，避免覆盖已有缺口；不伪造漏掉的运行；若恢复时观察期已结束，缺口截至观察终点。`overdue_intervals` 是该缺口内完整间隔数，不是已执行次数或平台丢失项目数。暂停操作另有事件，可区分已知暂停与未观察期间；不能仅凭缺口认定设备关机。

`schedule` 的退出码 0 表示控制或触发操作已处理，来源成功与否要查看嵌套 schedule 的 `last_result` 及对应运行报告；参数和存储错误为 2。计划和事件保存在 SQLite，不保存凭证或机会正文。各计划保留独立 ID 和历史数据，当前控制入口查看最近创建的计划；每日及观察期汇总可通过 `report` 查看，包含各计划的历史事件。

当前数据是本地候选，不应直接作为已核实的推送清单。

## 观察期报告

```bash
python3 -m opportunity_intake report --start 2026-10-22T00:00:00+00:00 --end 2026-10-23T00:00:00+00:00
```

替换为实际观察起止；按 UTC 的运行开始时间统计每日及全期结果，并列出查询预算、实际搜索范围、失败、截断和调度缺口。报告只含匿名统计与运行诊断，当前详情仍从 `list` 查看。来源删除导致历史身份缺失时会标记无法精确重算唯一数。历史近期数量按最后观察时刻，当前候选近期数量按导出时刻，不能相互替代。

[完整操作与统计口径说明](docs/observation-runbook.md)包含单次运行、抽查、有限期调度启停及汇总导出。自动化通过与单次实网成功均不代表多日稳定性；本次没有启动实际多日采集。

## 验证

```bash
python3 -m unittest discover -s tests -v
python3 -m venv temp/implementation-tools
temp/implementation-tools/bin/python -m pip install --cache-dir temp/pip-cache -r requirements-dev.txt
temp/implementation-tools/bin/mypy opportunity_intake tests
```

测试从完整采集入口进入，使用可控来源、时钟及真实临时 SQLite 存储；覆盖持久读取和去重、成功零条、部分失败、非法响应、坏记录隔离、超时、401／403／5xx、429 的两种等待格式和有界退避、请求／时间截断、进程退出恢复、数据库升级及批次回滚。推进可控时间验证等待期跳过和到期恢复，不进行真实退避等待。HTTP 适配通过本机测试服务器验证，自动化测试不依赖真实 Freelancer 账号。

增量采集测试另覆盖相同／变化内容的版本与整理结果、跨查询互斥计数、三天闭区间及未来时间、来源时间修正与缺失保全、预算和地域字段、旧候选兼容及 CLI 展示。已有摘要与分类仅作为隔离测试的前置数据。

复查测试覆盖搜索消失后的详情读取、跨重启轮转、共享预算、未知和失败状态保留、可靠关闭、网址变体排除、结束记录写入失败，以及真实子进程在写入结束记录后退出的恢复。以前的搜索专用用例显式设 `recheck_limit=0`，新用例覆盖开启复查后的完整运行。

来源删除测试通过公开删除入口和完整采集运行检查：活跃／已结束项目清理、同网址追踪变体、不同身份参数和来源隔离、历史引用与复查游标清理、限流保留、重复删除、再次入库、CLI 参数及结果。数据库故障注入验证跨表回滚，真实子进程分别在事务中和提交后退出，重开状态后验证重试语义。

调度测试覆盖跨重启次数上限、暂停／恢复／停止、观察终点收紧请求窗口、过期恢复缺口、限流推迟、可控等待的前台执行器、真实跨进程重叠、进程退出释放锁及批次恢复、结束报告已保存而调度写入失败后的核对。CLI 控制测试不发起网络读取。本次没有创建实际多日计划或启动实网定时采集。

项目搜索与详情参数依据 [Freelancer 官方 SDK 的 search_projects](https://github.com/freelancer/freelancer-sdk-python/blob/master/freelancersdk/resources/projects/projects.py)；本实现只使用项目搜索和项目详情的 GET 请求。

2026-10-20 实网检查：两轮各一个请求、每轮最多两条。第一轮新增两条，第二轮新增零条、重复两条，数据库保留两条候选及两份运行报告。两轮都因样本上限标记为部分完成；没有验证多日稳定性或候选的绘画相关性。

## 需求与工单

- [持续采集实验规格](.scratch/freelancer-continuous-intake/spec.md)
- [工单 01](.scratch/freelancer-continuous-intake/issues/01-manual-persistent-collection.md)
- [工单 02](.scratch/freelancer-continuous-intake/issues/02-bounded-failure-safe-runs.md)
- [工单 03](.scratch/freelancer-continuous-intake/issues/03-incremental-change-and-recency.md)
- [工单 04](.scratch/freelancer-continuous-intake/issues/04-status-recheck-and-ended-records.md)
- [工单 05](.scratch/freelancer-continuous-intake/issues/05-source-deletion-requests.md)
- [工单 06](.scratch/freelancer-continuous-intake/issues/06-bounded-scheduling-and-resume.md)
- [工单 07](.scratch/freelancer-continuous-intake/issues/07-observation-report-and-verification.md)
- [领域术语](CONTEXT.md)
- [保留的历史原型](temp/prototype-opportunity-lab/README.md)
