# Freelancer 持续采集实验

Type: spec
Status: ready-for-agent
Created: 2026-10-20
Testing boundary: 用户已确认采用“一次完整采集运行”作为主要测试入口。

## Problem Statement

项目运营者希望持续发现海外绘画约稿机会，供国内已有接单能力的个人画师自行筛选和申请。自动采集是首版前提。目前仅有一次性读取脚本、历史样本和模拟流程，无法判断来源是否能够持续提供新机会，也无法在程序重启后可靠地保留去重、复查及结束处理结果。

现有原型每次按 illustration、portrait 两组关键词各读取最多五条 Freelancer 项目，覆盖输出快照。中文摘要来自对旧样本的人工整理，新项目保持待判断。模拟结束记录与每日摘要不能证明真实持久保存或通知已经实现。

2026-10-20 的一次独立只读检查取得 HTTP 200、API success 和五条含正文、发布时间、预算及状态字段的项目。该证据仅证明当次读取成功，不证明这五条均为约稿机会，也不证明持续稳定性、总供给或本产品的数据使用许可。

## Solution

建立一个范围有界的 Freelancer 持续采集实验，让项目运营者能够配置并重复执行采集，在本地持久保存当前候选、识别重复及正文变化、复查接单状态，并查看每次运行和整个观察期的结果。

实验交付的核心行为是：来源读取 → 结束记录排除 → 候选规范化与持久保存 → 已存候选状态复查 → 确认结束后的记录及详情删除 → 运行报告。单次手动运行与定时执行共享同一流程。

本阶段取得的是“采集候选”和可核查的运行证据。关键词命中不直接认定为约稿机会或可推送机会；新增和内容变化的候选保持待整理，供人工抽查和下一阶段自动分类、中文摘要使用。

## User Stories

1. As a project operator, I want to run one complete collection cycle manually, so that I can verify its behavior before enabling a schedule.
2. As a project operator, I want scheduled collection to use the same entry point as manual collection, so that both modes produce consistent results.
3. As a project operator, I want to configure queries and request limits, so that each experiment has a clear and bounded collection scope.
4. As a project operator, I want to configure the schedule and observation period, so that collection stops at the intended time.
5. As a project operator, I want to pause and resume collection, so that I can control resource use without losing saved candidates.
6. As a project operator, I want credentials to remain outside stored project data and reports, so that inspection does not expose secrets.
7. As a project operator, I want source project IDs and URLs to be preserved, so that I can identify and inspect the original records.
8. As a project operator, I want overlapping queries and repeated runs to update the same candidate, so that counts and saved records are not duplicated.
9. As a project operator, I want original publication time to remain distinct from discovery and check times, so that recent supply is measured correctly.
10. As a project operator, I want missing or invalid publication times to remain unknown, so that they are not presented as verified recent opportunities.
11. As a project operator, I want original budgets, currencies, and pricing units to be retained, so that later processing does not confuse hourly rates and fixed prices.
12. As a project operator, I want undisclosed budgets and geographic eligibility to remain explicit, so that missing information is not converted into a false assurance.
13. As a project operator, I want keyword matches to remain unreviewed candidates, so that search results are not mistaken for confirmed drawing commissions.
14. As a project operator, I want new or changed descriptions to require fresh classification and summary, so that stale conclusions are not reused.
15. As a project operator, I want saved candidates to survive process restarts, so that continuous observation does not depend on an open page or session.
16. As a project operator, I want incomplete or failed requests to be distinguishable from successful empty results, so that an outage does not look like an absence of supply.
17. As a project operator, I want failed requests to leave existing candidates intact, so that temporary access problems do not remove useful records.
18. As a project operator, I want stored candidates to be checked independently of search results, so that disappearing from an active list does not hide an actual status change.
19. As a project operator, I want inaccessible or ambiguous status checks to remain unresolved, so that they are not reported as confirmed endings.
20. As a project operator, I want confirmed endings to create durable ended records before details are deleted, so that later discovery cannot reintroduce the same project.
21. As a project operator, I want an ended-record write failure to preserve the candidate, so that a storage error cannot destroy the information needed for recovery.
22. As a project operator, I want rediscovered ended URLs to be excluded before further processing, so that ended projects do not consume later classification or publication work.
23. As a project operator, I want explicit source deletion requests to remove related retained data, so that the established deletion exception can be honored.
24. As a project operator, I want overlapping runs and interrupted writes to recover safely, so that they do not duplicate records or corrupt collection state.
25. As a project operator, I want authentication errors and rate limits to stop or defer requests predictably, so that failures do not trigger uncontrolled repeated access.
26. As a project operator, I want each run to report its scope, failures, and result counts, so that I can assess what was actually observed.
27. As a project operator, I want daily and observation-period reports to distinguish candidates from reviewed opportunities, so that supply estimates are not overstated.
28. As a project operator, I want to inspect the currently retained candidate set, so that I can manually sample relevance and compare it with source pages.
29. As a project operator, I want reproducible automated checks without live source access, so that behavior can be verified even when the source is unavailable.
30. As a project operator, I want the experiment to remain separate from the preserved prototype, so that earlier evidence is not overwritten by implementation or new observations.

## Implementation Decisions

### 范围与主要接口

- 以“一次完整采集运行”为主要应用接口，接受运行配置、当前时间、来源访问能力及持久保存能力，产出持久状态变化和结构化运行报告。定时调度仅触发同一入口，不另建一套采集业务逻辑。
- 复用原型已经验证的 Freelancer 搜索、详情重读和字段语义作为参考；原型保留为证据，新的持续流程独立实现。旧页面、静态摘要和模拟记录不直接成为生产流程。
- 内部可划分来源适配、规范化、候选与结束记录保存、报告及调度职责，但不为每个辅助函数建立独立公共接口。选用何种存储库与调度工具由实施时决定，以满足本规格的外部行为为准。
- 保持单进程或单实例运行的实验规模。一次运行尚未完成时，下一次触发应跳过或排队，并在报告中说明；不并发修改同一份状态。

### 有界读取与调度

- 初始搜索范围沿用原型的 illustration、portrait 两组词，每组最多五条、每组一页。查询词、页数和条数可配置，调整后必须记录实际配置和是否完整执行。
- 所有搜索及详情复查共同受每轮总请求上限和总耗时上限约束。请求上限、超时、复查批量和运行频率作为显式配置；缺少有效上限时不启动自动运行。
- 本阶段不预设未经确认的高频率或全站扫描。达到页数、请求或耗时上限时，标记结果为截断或部分完成，不声称覆盖了整个时间窗口。
- 未提供定时配置时只运行一次。启用定时实验时必须给出运行频率和观察期终点或最大运行次数，能够停止、恢复和查询最近一次结果。
- 暂不要求选定云服务或全天在线机器。进程或机器停止期间不声称持续运行；恢复后记录观察缺口，不虚构漏掉的历史项目。
- 401、403 停止本轮后续来源请求并报告；429 按来源给出的等待信息推迟后续运行，无等待信息时采用有界退避。网络错误、5xx 和响应解析错误均计入失败，不无限重试。
- 凭证仅从外部配置注入，不出现在命令行明文、候选、报告或导出内容中；不将历史匿名成功当作长期匿名访问保证。

### 候选数据、增量与时间

- 候选以“来源 + 稳定项目 ID”为身份；保留原网址，并根据来源生成规范化网址。仅移除已知不影响帖子身份的追踪参数，不能移除决定项目身份的路径或参数。
- 先查结束记录，再进行候选整理和写入。搜索响应若已包含正文，仍不对已结束记录进行后续摘要、候选更新或额外详情请求。
- 保存必要字段：来源、稳定 ID、原网址及规范化网址、标题、当前必要正文、原始发布时间、首次发现时间、最近读取时间、最近成功状态核验时间、原币种预算区间、计价单位、来源原始状态、接单状态、整理状态及内容版本标识。未知字段显式为空或未知，不编造值。
- 原始发布时间、首次发现时间和最近检查时间独立保存。缺失、无效或无法可靠解析的原始时间不以采集时间补齐；不计入已验证的最近三天候选数。
- 最近三天按原始发布时间和运行时刻计算；内部时间统一带时区，报告注明统计时区。预算保留原币种和固定总价／时薪等来源单位，不用投标均价替代预算。
- 同轮重复、跨查询重复、跨轮重复及重启后的重复均更新同一候选。再次发现不重写首次发现时间；来源原始时间或内容确有更新时保留最新可核查值，不伪造发布时间。
- 新候选标为待整理。影响分类或摘要的正文等输入发生变化时使已有整理结果失效；变化与不变的记录分别计数。无可靠依据时不把“地域未说明”改成接受中国画师。
- 本阶段不接入自动分类或摘要模型，不依据关键词直接产生可推送机会。人工抽查不成为人工录入替代自动采集的运营方式。

### 状态复查与结束记录

- 对已存候选安排独立的详情复查，不能只复查本轮仍出现在 active 搜索中的项目。采用有界、可恢复的轮转，报告待复查数量及最近成功核验时间，避免请求预算不足时永远遗漏部分候选。
- active/open 等来源状态仅作为本次观察，不保证仍可承接。大量申请、正在挑选、候选未出现在搜索结果、超出三天窗口、404 或读取失败均不足以自动认定结束。
- 只有来源明确关闭或需求方明确表示已找到承接者等可靠证据才能触发结束。无法确定的状态保留候选并标注无法核实。Closed 可以表示结束，不自动解释为已成交。
- 普通结束处理必须先持久写入独立结束记录，再删除机会详情。结束记录仅保留原帖网址、来源标识、删除时间和删除原因，不保留标题、正文、中文摘要、预算或需求方资料。
- 普通结束记录长期保留，支持同网址及其不改变身份的变体排除。去重索引不得成为另一份长期保存机会详情的历史库。
- 结束记录写入失败时保留详情并记录失败。写入成功但删除前进程中断时，下一次运行先按结束记录排除并补完详情删除；不得重新暴露或重新整理该候选。
- 已确认结束后的详情清理应覆盖应用维护的副本与导出缓存；运行历史只保留必要计数和不含机会详情的诊断信息。报告不能变成正文或预算的历史备份。
- 提供可显式调用的来源删除处理能力。遇来源平台或原作者明确删除要求时清除关联详情、缓存、结束记录中的网址及相关索引；接受之后无法靠原记录阻止重新发现。普通需求结束不走此例外流程。
- 仅超出三天窗口的候选不自动写入结束记录。具体观察期的数据保留上限与来源要求分别记录，不把时间窗口当作来源已结束的证据。

### 持久保存、故障与报告

- 候选、独立结束记录、运行进度及必要运行汇总使用持久存储，程序退出或重启后仍可读取。长期运行状态不放入一次性临时目录。
- 一次失败或部分完成不能用空结果覆盖整个已存候选集合。单条记录无效时隔离并计数；响应整体无效时标记该请求失败。
- 中断恢复后允许再次读取来源，但重复处理不得增加候选副本或重复普通结束记录。状态持久化损坏应明确报错，不静默重建为空库。
- 每次运行记录开始／结束时间、配置范围、请求尝试数、成功／失败数、失败类别、实际取得条目数、唯一 ID 数、新增数、重复／变化数、结束记录命中数、详情复查数、确认结束数、字段缺失、待整理及待复查数量，并说明结果是否完整。
- 搜索正常返回零条与请求失败、部分查询失败、达到上限分别报告；总体状态至少能够区分成功、部分完成、失败和跳过。
- 汇总观察期内的运行次数、失败及缺口、去重新增候选数、已知原始发布时间在最近三天的候选数、字段覆盖率和状态核验情况。各统计必须注明分母及查询范围。
- 字段覆盖率和近期数量基于实际取得的候选，不外推为平台全量。未经人工或后续自动分类核验的候选数不得称为有效约稿数量；本阶段人工相关性结论在抽查记录中单列。
- 允许查看当前保留候选及必要汇总，供人工抽查。实验不发邮件、不投标、不联系需求方，也不自动公开发布来源内容。

## Testing Decisions

- 用户已确认主要测试入口为“一次完整采集运行”。测试通过该入口驱动配置、来源响应序列与时间，检查持久保存后的可读结果、运行报告及必要的来源请求范围；不依赖内部函数调用次数、私有数据结构或具体存储库。
- 主要覆盖完整采集流程，包括来源适配、字段处理、增量保存、状态复查和结束处理；通过可控来源端点或等价替身提供成功、空结果、变化、结束及错误响应。使用真实的隔离测试存储，能够跨两次应用启动验证持久性。
- 故障注入限定在来源和存储边界，例如模拟结束记录写入失败或写入后中断。不能通过仅让所有存储操作成功的内存替身宣称持久保存已验证。
- 定时调度只检查是否在配置时间调用同一入口、是否遵守停止条件、是否避免重叠，不另建第二套业务断言。使用可控时间推进，不让自动化测试真实等待数天。
- 当前未发现已有自动化测试套件。可参考原型已演示的“重复发现、无法核实、结束记录写入失败、成功记录后排除再次发现”等行为，并将其扩展为真实持久保存的验收；不以页面内存模拟代替这些测试。

必须覆盖以下外部行为：

1. **首次运行与重跑**：两组查询含重叠 ID，首次只保存唯一候选；下一轮及重启后再次运行仍不重复，首次发现时间保持一致。
2. **字段真实性与边界**：发布时间恰在三天边界内外、发布时间未知或无效、预算未知、固定价与时薪、地域未说明均有正确保存和统计；不以采集时间或投标均价补值。
3. **内容变化**：相同输入保持同一内容版本；正文变化更新候选并使旧整理结果失效，不复用旧摘要。
4. **空结果与失败**：成功零条、网络失败、非法响应、部分查询失败分别报告；原有候选不因失败丢失。
5. **状态复查**：候选不再出现在搜索中时仍有机会轮转复查；读取失败、404、含糊状态及正在挑选均不触发普通结束删除。
6. **确认结束与再发现**：详情明确关闭后写入最小结束记录并清除详情；同网址和已知追踪参数变体再次出现时不重新入库或整理，不误排不同项目。
7. **结束写入故障与恢复**：写结束记录失败时详情保留；写成功后、删除前中断，重启后补完删除并保持排除；报告及缓存不残留应删除的详情。
8. **来源删除要求**：显式来源删除能够清除详情、关联缓存及结束网址和索引；不同项目不受影响；清除后的去重能力不被虚假声称仍然保留。
9. **请求边界与限流**：页数、总请求量和耗时不越配置上限；401／403 停止后续请求；429 推迟后续运行；不得无限重试或把截断当完整成功。
10. **中断、并发与调度**：中断后可继续；重叠触发不产生双份记录；到观察期终点停止；恢复后明确记录停机缺口。
11. **报告可核对性**：新增、重复、变化、结束、失败、缺失和待复查等数字可由测试输入与持久结果核对；报告中没有凭证和机会正文历史副本。
12. **实验范围**：自动化测试不依赖真实 Freelancer、模型、邮件或用户账号；运行过程中不发生投标、消息发送或公开发布。

实网验证另行记录：在配置完整的环境完成一次有界只读冒烟检查，再按选定观察期运行并汇总。短时间自动化测试通过和一次实网成功均不能替代多日稳定性证据。

## Out of Scope

- 自动 AI 分类与中文摘要、模型供应商选择、模型成本及质量评估；保留后续接入所需的待整理与内容变化状态。
- 面向画师的网站、登录、搜索订阅界面、真实每日摘要发送、邮件发送去重和投递服务。
- 人民币参考预算换算、汇率服务、正式项目类型分类表、中英文关键词扩展以及用户最低预算匹配规则。
- Upwork 浏览器采集、VGen 买方入口续查、Workana、PeoplePerHour 等新增来源接入；这些来源保留在项目原有研究或测试范围。
- 全站遍历、平台总供给估计、历史项目完整回补、分布式采集、高可用部署和承诺全天在线。
- 自动申请、投标、代沟通、报价、成交或收款协助。
- 付费测试、收费方案、种子用户招募以及固定的付费或回复人数门槛。
- 把接口可读、持有凭证或免费首版解释为已取得公开运营、存储、摘要或再展示许可。
- 本次规格发布不执行采集实现、不启动多日定时任务、不申请凭证，也不向外部联系人发送消息。

## Further Notes

### 已有决定、规格设计与未完成验证

- 用户已经确认：自动采集优先于网站；Freelancer 为首个实验对象；首版服务国内已有接单能力的个人画师；绘画接稿首发、个人委托优先，同时保留商业插画范围。
- 用户在本轮明确确认：采用完整采集运行作为主要测试入口。其余技术安排是本规格基于现有讨论给出的实施设计，不记作用户此前逐项选择过的决定。
- 3–7 天是前一轮提出的观察期建议，不是用户确定的固定周期或继续投入门槛。实际运行需记录选定起止、频率、请求上限与执行环境；这些参数可以配置，无需重新访谈产品方向。
- 原有六周探索周期的起止尚未确定；本规格不推算起点，也不改变用户自行判断是否继续投入的决定。
- 尚未完成的来源用途、费用、限额和保留要求继续单列核实。此规格不替平台作出许可结论，不取消既定中文摘要需求；对外发布与本地实验保持清晰的状态区分。
- 观察结果无论项目多少都应如实报告，包括空结果、非绘画候选、字段不足与访问失败。技术验收关注行为正确与证据可核对，不设置最低供给数量或转化门槛。
- 后续可按此规格拆分实施工单；本次不额外创建工单或修改旧原型工单的完成状态。

### 参考证据

- [领域术语](../../CONTEXT.md)
- [已确认需求与未决问题](../../docs/discovery.md)
- [原型工单与实验边界](../opportunity-intake/issues/01-prototype-evidence.md)
- [原型运行说明](../../temp/prototype-opportunity-lab/README.md)
- [首个来源的历史研究](../../docs/research/project-platform-selection.md)：历史研究证据，不视为当前条款复核。
- [2026-10-20 有界只读检查](../../temp/project-review-2026-10-20/freelancer-read-check.json)：一轮五条，仅验证当次读取与字段存在。
