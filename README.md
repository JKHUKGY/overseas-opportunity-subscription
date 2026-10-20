# 海外绘画约稿机会采集实验

当前实现：工单 01–02，手动读取 Freelancer 候选、持久保存和去重，并在请求失败、限流或进程中断时保全已完成进度。运行依赖 Python 3.9+ 和 curl；运行时无需安装 Python 第三方包。

## 使用

从项目根目录运行：

```bash
python3 -m opportunity_intake run
python3 -m opportunity_intake list
python3 -m opportunity_intake runs
```

每次 `run` 执行一轮并退出。默认查询 illustration 和 portrait，每组一页、最多五条；全轮最多两个请求，每个请求最多 20 秒，来源读取窗口最多 40 秒。可显式调整：

```bash
python3 -m opportunity_intake run --query illustration --limit 2 --max-requests 1 --request-timeout 10 --max-seconds 12
```

`--query` 可重复提供；`--pages` 控制每个关键词最多读取多少页，所有查询共享 `--max-requests` 预算。单页不足设定条数时停止该词的分页。页数或请求预算限制了进一步读取时，报告会明确 `truncated: true`，不会将样本说成平台全量。

数据默认存入项目的 `data/freelancer.sqlite3`，不进入 Git。`run`、`list`、`runs` 都可用 `--state` 指定另一份持久状态；查看命令要求该状态已经存在。测试与一次性验证文件使用项目 `temp/`。

需要凭证时从 `FLN_OAUTH_TOKEN` 环境变量读取，CLI 不提供令牌参数。传给 curl 时使用标准输入，不写入命令行、状态和运行报告；HTTP 错误只保留类型与状态码，不保存原始错误响应或需求方账户对象。正常情况下可先使用未配置令牌的有界只读运行，是否允许访问以实际结果为准。

## 保存内容与结果含义

候选包含来源和稳定 ID、原网址与规范化网址、标题、来源返回的当前需求正文、原始发布时间、首次发现和最近读取时间、原币种预算与计价方式、来源状态、待整理状态。没有可靠值的字段保持未知；暂不读取附件、图片或评论，也不生成 AI 中文摘要。

“必要正文”在本工单中具体使用来源返回的 `description`，缺失时使用 `preview_description`；不会下载完整网页、附件或扩展需求方资料。最近成功详情核验时间为空，因为本工单尚未实施详情状态复查。地域资格标记为“地域未说明”，未作申请资格核验。

相同来源及 ID 更新同一候选，保留首次发现时间、已有处理状态、接单状态和最近成功核验时间。每次成功请求的候选与运行进度在同一个 SQLite 事务内提交；某一批写入失败只回滚该批，不清空此前成功保存的数据。旧版本数据库会自动从 schema 1 升到 2，保留候选及报告；无法识别或损坏的状态会明确报错。

报告中 `received_count` 是实际返回条目数，`unique_count` 是本轮有效候选的不同 ID 数，`new_count` 是新入库数，`duplicate_count` 是有效条目中已存在或同轮重复的次数，`invalid_count` 是本轮处理范围内身份无效的记录数。达到配置条数后的额外响应不入库。未知字段不等于无效身份；这些数量均不代表已经确认的约稿机会数。

`requests` 按实际请求顺序记录关键词、偏移量、请求条数、成功／失败及返回条数；失败时附错误类型和可用的 HTTP 状态。由此可以区分“计划查询但因预算没有执行”和“确实执行后返回零条”。运行历史不包含来源正文或凭证。较早版本的实网验证报告可能没有该字段。

运行结果如下：

| 状态 | 含义 |
| --- | --- |
| `success` | 计划范围正常完成，允许零条结果 |
| `partial` | 达到分页／条数／请求或时间上限、存在坏记录，或部分请求失败 |
| `failed` | 来源请求全部失败 |
| `skipped` | 尚在来源等待期，本轮没有访问来源 |
| `running` | 已保存启动或进度记录，但尚无结束记录 |

CLI 对成功／部分完成／跳过返回 0，来源失败返回 1，配置或存储错误返回 2。调用方应同时检查 JSON 状态及 `truncated`。搜索请求共用总请求预算和来源读取窗口，每次超时取配置与剩余窗口的较小值；窗口用尽后不再发起请求。最后的本地持久化仍会完成，因此命令的总墙钟时间可能长于来源读取窗口。

运行开始及每次请求发出前都会保存进度；进程意外退出后，已完成批次仍然可读。下次运行的 `unfinished_run_ids` 列出没有结束记录的历史运行。这些记录可能属于意外中断，也可能属于另一个仍在执行的进程；本工单不实现并行调度和运行锁。恢复时重新读取来源，通过稳定 ID 去重，不假定失败页已经完成。

所有来源错误都会停止本轮后续请求并保留成功批次，401／403 不自动重试。错误报告区分 HTTP 状态、`timeout`、`transport_error`、`transport_unavailable`、`invalid_json`、`invalid_response` 和 `api_error`；单条坏记录计入 `invalid_count`，有效记录继续保存。

429 优先采用 [HTTP Retry-After](https://www.rfc-editor.org/rfc/rfc9110.html#name-retry-after) 的秒数或 HTTP 日期，写入 `next_allowed_at`。缺失或无效时从 60 秒开始翻倍，最高 3600 秒；来源请求成功完成且没有请求失败时重置退避。等待时间与限流次数持久保存，重启后仍有效；未到期的完整运行记为 `skipped`，附 `skip_reason: source_cooldown`，到期后可再运行。程序不在等待期内睡眠重试，也不把原始等待响应、正文或凭证写入报告。

正文版本变化、真实结束记录、来源删除、定时调度和观察期汇总属于后续工单。当前数据是本地候选，不应直接作为已核实的推送清单。

## 验证

```bash
python3 -m unittest discover -s tests -v
python3 -m venv temp/implementation-tools
temp/implementation-tools/bin/python -m pip install --cache-dir temp/pip-cache -r requirements-dev.txt
temp/implementation-tools/bin/mypy opportunity_intake tests
```

测试从完整采集入口进入，使用可控来源、时钟及真实临时 SQLite 存储；覆盖持久读取和去重、成功零条、部分失败、非法响应、坏记录隔离、超时、401／403／5xx、429 的两种等待格式和有界退避、请求／时间截断、进程退出恢复、数据库升级及批次回滚。推进可控时间验证等待期跳过和到期恢复，不进行真实退避等待。HTTP 适配通过本机测试服务器验证，自动化测试不依赖真实 Freelancer 账号。

项目搜索参数依据 [Freelancer 官方 SDK 的 search_projects](https://github.com/freelancer/freelancer-sdk-python/blob/master/freelancersdk/resources/projects/projects.py)；本实现只使用公开项目搜索的 GET 请求。

2026-10-20 实网检查：两轮各一个请求、每轮最多两条。第一轮新增两条，第二轮新增零条、重复两条，数据库保留两条候选及两份运行报告。两轮都因样本上限标记为部分完成；没有验证多日稳定性或候选的绘画相关性。

## 需求与工单

- [持续采集实验规格](.scratch/freelancer-continuous-intake/spec.md)
- [工单 01](.scratch/freelancer-continuous-intake/issues/01-manual-persistent-collection.md)
- [工单 02](.scratch/freelancer-continuous-intake/issues/02-bounded-failure-safe-runs.md)
- [领域术语](CONTEXT.md)
- [保留的历史原型](temp/prototype-opportunity-lab/README.md)
