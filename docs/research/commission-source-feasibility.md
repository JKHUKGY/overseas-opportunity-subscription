# 海外约稿来源：获取可行性与真实样本

核查日期：2026-09-18。依据：[当前业务探索记录](../discovery.md)、[领域术语](../../CONTEXT.md)。本报告补充[首轮研究](commission-sources.md)，不替用户新增产品决策。

2026-09-22 范围更新：用户已明确将信息收集资源优先投入 Upwork 这类集中式项目平台，社交媒体作为补充。下文保留 9 月 18 日的研究事实与当时建议，来源推荐顺序不再代表当前实施优先级；下一轮需补查项目平台后选择首个采集验证目标。

## 结论与推荐顺序

**海外公开付费约稿帖确实存在；本轮尚未证明有一个来源同时满足稳定获取、允许本产品存储再展示、最近三天供给充足。** 因而现在可以着手来源验证，不能宣布已经具备自动运营所需的数据。

1. **Reddit 最值得核实接入资格。** HungryArtists、artcommissions 均有明确买方样本，部分需求方会更新结束状态；但 API 使用须事先批准，商业使用另需书面许可。首版免费不能自动视为非商业豁免。[Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy)
2. **Bluesky 适合下一步小量技术验证，但本轮调用没有成功。** 官方提供搜索和线程接口；一次公开搜索请求返回 HTTP 403，未绕过访问限制。不能据此断言它不能接，也不能声称已跑通。[搜索接口定义](https://raw.githubusercontent.com/bluesky-social/atproto/main/lexicons/app/bsky/feed/searchPosts.json)、[线程接口定义](https://raw.githubusercontent.com/bluesky-social/atproto/main/lexicons/app/bsky/feed/getPostThread.json)
3. **Polycount 可以补充漫画、游戏美术需求，授权仍待解决。** 有个人同人漫画买方原帖；其用户内容许可带 NonCommercial 条件，不应把免费试运营自动当作许可成立。[同人漫画原帖](https://polycount.com/discussion/238848/paid-manga-artist-needed-who-can-create-a-fanmade-manga)、[服务条款 §3](https://polycount.com/discussion/193727/terms-of-service)
4. **X 列为有预算后的比较候选；Upwork 暂不纳入首版自动源。** 具体条件见下表。没有为本次研究申请账号、权限、购买额度或联系需求方。

## 来源矩阵

“能读到”是技术事实；“允许持续整理并展示”是用途与权限问题；“数据够用”还需要实测。三者分开判断。

| 来源 | 获取方式、账户与费用 | 评论／更新与数据适配 | 摘要存储、再展示与删除约束 | 当前判断 |
|---|---|---|---|---|
| Reddit：HungryArtists / artcommissions | [官方 API](https://www.reddit.com/dev/api/)；须先获批准，商业用途书面许可；本产品具体报价未知。[访问政策](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy) | 可访问帖子与评论的官方能力已存在；本轮仅查公开页面及其搜索快照，未获 API 权限、未实测持续采集。买方帖、预算与关闭信号见下文样本。 | AI 摘要、缓存范围、展示、向第三方模型传输要落在获批用途内；[API 条款](https://redditinc.com/policies/data-api-terms)及[开发者条款 §7.3](https://redditinc.com/policies/developer-terms)限制保留并要求相应删除。长期留原帖 URL 是否允许，未确认。 | 需求匹配强；接入条件未满足。 |
| Bluesky | 官方推荐公共网页用途使用 `public.api.bsky.app`；限额依服务而异，未取得本场景的具体保证或计费报价，不能承诺无限免费。[限流说明](https://bsky.network/docs/rate-limits/) 本轮无登录请求返回 403。 | `searchPosts` 支持关键词、时间、排序；`getPostThread` 可返回回复结构。搜索时间按 `sortAt`，可能不等于 `createdAt`；游标不保证遍历全部结果。[搜索定义](https://raw.githubusercontent.com/bluesky-social/atproto/main/lexicons/app/bsky/feed/searchPosts.json)、[线程定义](https://raw.githubusercontent.com/bluesky-social/atproto/main/lexicons/app/bsky/feed/getPostThread.json) | 用户保有内容权利，开放协议不等于任意再利用许可；本产品中文摘要＋邮件分发授权边界未核实。[服务条款 §3](https://bsky.social/about/support/tos) 所有服务须有响应用户删除请求的方法；长期 URL 记录是否兼容待确认。[开发者指南](https://bsky.network/docs/developer-guidelines/) | 技术文档适合试验；实际买方样本、可用连接、展示条件待验证。 |
| Polycount Freelance Job Postings | 公开网页可读，回复需登录；本轮未找到官方批量需求 API、自动采集审批途径或报价。[版块](https://polycount.com/categories/freelance-job-postings) | 官方规则定位付费自由职业，可更新首帖和追加变更；申请通常走原帖提供的联系方式，评论少不代表无人申请。[规则](https://polycount.com/discussion/136571/freelance-jobs-guidelines) | 用户内容为 CC BY-NC-SA 3.0；聚合项目是否满足 NC、摘要的许可义务需确认。自动读取许可、来源删除同步的专门期限和 URL 长期留存均未核实。[条款](https://polycount.com/discussion/193727/terms-of-service) | 已发现绘画买方；作为补充来源，未批准正式自动接入。 |
| X | Recent Search 覆盖七天，需开发者账号、应用和令牌；帖子读取按返回资源计费，当前每条 $0.005，需预充值。[搜索说明](https://docs.x.com/x-api/posts/search/introduction)、[定价](https://docs.x.com/x-api/getting-started/pricing) | 可搜索原帖和公开回复，但本轮未调用付费接口、未测绘画买方密度；作者未公开的私下成交仍无法知道。 | 使用范围需披露并符合政策；展示应同步内容变化，删除要求有时限。摘要与邮件再分发、永久 URL 记录是否符合获批用途未确认。[开发者政策](https://docs.x.com/developer-terms/policy) | 可预算化的第二梯队，未证明供给。 |
| Upwork（对比） | 商业 API 仅限事先获书面许可的精选合作伙伴；价格未知。[商业 API 说明](https://support.upwork.com/hc/en-us/articles/17995890765459--Commercial-API-use) | 不能把 API key 当作持续监控或抓取许可。[自动化说明](https://support.upwork.com/hc/en-us/articles/43342677368467-Use-bots-and-other-automation-properly) | 2026-08-13 生效 API & MCP 条款限制批量持续枚举；通常缓存至多 24 小时，更长保存有额外条件，另有删除要求。当前集中机会库与永久 URL 记录需专门确认。[现行条款 §3.5、§8](https://www.upwork.com/legal#apimcpterms) | 首版排除，除非获得匹配本产品的授权。 |

本轮研究时未将 VGen 列为买方供给源：当时未补出公开买方目录或批量许可，沿用首轮“不能把画师服务菜单当需求池”的待验证结论。[首轮证据](commission-sources.md#2-vgen)。2026-09-22 用户随后明确要求将 VGen 纳入来源测试，当前测试范围以该决定为准；加入测试不代表买方供给已验证。

## 八个真实买方历史样本

**目标窗口是 2026-09-15 02:59 UTC 至 2026-09-18 02:59 UTC。未获得足够可核实的窗口内买方样本。** 带日期的 Reddit 搜索主要返回已移除帖；例如 [9 月 16 日移除记录](https://www.reddit.com/r/artcommissions/comments/1whqfdf/removed/)只有版规处理文本，无法还原买方需求，不计为机会。Bluesky 查询失败。以下明确使用历史样本，不作为今天可申请清单，也不据此估算每天的供给量。

表中“未见结束”仅指本次取得的原帖页面或索引快照；搜索工具可能提供缓存、部分评论，不能等同于实时全线程核验。所有八条的承接者地域均未明确说明；不据英语、平台或角色设定推断需求方国籍。仅出现 `$` 或 `dollars` 时不擅自填 USD。日级日期没有时区和时分秒，不人为补零生成精确时间。

| 原帖／来源 | 发布时间与精度 | 需求及付费证据 | 接单状态依据与取样限制 |
|---|---|---|---|
| [宠物鱼纪念肖像／HungryArtists](https://www.reddit.com/r/HungryArtists/comments/1vml122/hiring/) | 2026-08-12；原站搜索索引日级，页面为相对时间 | 两条宠物鱼的纪念画；预算 50–60 `$`，具体币种未明示 | 快照未见需求方结束声明；机器人只说明如何使用结束指令，不是成交证据。 |
| [Halo 角色半身像／artcommissions](https://www.reddit.com/r/artcommissions/comments/1uwvj15/hiring_looking_for_someone_to_do_a_halfbody_art/) | 2026-07-15；原站搜索索引日级 | 角色半身像；30–95 `$`，允许略高，具体币种未明示 | 页面评论已锁；未取得需求方明确成交声明，**不能仅因锁帖判已接走**。 |
| [音乐单曲封面／HungryArtists](https://www.reddit.com/r/HungryArtists/comments/1ubajno/hiring_70_dollars_for_a_cover_of_my_music_single/) | 2026-06-20；索引日级 | 单曲封面，70 dollars，具体币种未明示；个人音乐发布用途 | 原帖索引明确显示正文编辑为 Position Filled，应过滤；原帖页面在初次核查可打开，复核超时，缓存新鲜度无保证。商业使用细节未确认。 |
| [科幻 OC 角色设定图／artcommissions](https://www.reddit.com/r/artcommissions/comments/1o7tw7n) | 2025-10-16；索引日级 | 自己故事中的类人角色设定，150 USD | 索引快照未见结束；直接打开失败，不能认定当前仍开放。 |
| [PF2E 角色绘画／artcommissions](https://www.reddit.com/r/artcommissions/comments/1kwc7xm) | 2025-05-27；索引日级 | 桌游角色；160–200 USD，无硬截止日期 | 需求方正文写 CLOSED，并描述约一天内看完作品集并作出选择；有明确结束证据。直接打开失败，依据为原帖索引快照。 |
| [首个 OC 的设计完善／artcommissions](https://www.reddit.com/r/artcommissions/comments/1ketmq2/hiring_anime_style_character_designer/) | 2025-05-04；索引日级 | 动漫风角色设计和草图，明确提出分两次付款；预算未披露 | 快照未见结束声明；这是“明确付费但无金额”例，不把画师评论报价当买方预算。 |
| [作者社交账号肖像／HungryArtists](https://www.reddit.com/r/HungryArtists/comments/1fkqkmv) | 2024-09-19；索引日级 | 半写实数字肖像，偏好不超过 100 `$`，具体币种未明示 | 需求方更新称仍在挑选、可能几小时后决定；属于“正在挑选”的历史证据，不能跨两年当当前进展。 |
| [One Piece 黑白同人漫画／Polycount](https://polycount.com/discussion/238848/paid-manga-artist-needed-who-can-create-a-fanmade-manga) | 2026-07-14；原帖日级 | 需求方已有剧本，找漫画画师；标题明确 PAID，预算未披露 | 取得页面未见结束，原帖有申请联系方式；仅取样，不转载联系方式，不判断目前可接。 |

这些样本证明买方意图与可提取字段存在，**不证明需求方身份真实性、支付能力、中国画师成交率或现在仍有效**。

## 样本直接暴露的判断陷阱

- **不能只认 `[Hiring]`＋金额。** [这条 2026-06-04 的全身角色帖](https://www.reddit.com/r/HungryArtists/comments/1twa2yd/hiring_full_body_artwork_100_budget/)标题和预算看似合格，正文却明确说是假帖。它是排除样本，不计入上面的八条买方样本。
- **机器人模板不能当作需求方状态。** HungryArtists 官方指引及机器人会解释结束指令；需要核对发言者、上下文和实际状态，不能全文命中 `Position Filled` 就删。[需求方指南](https://www.reddit.com/r/HungryArtists/wiki/client/)、[实际机器人模板](https://www.reddit.com/r/HungryArtists/comments/1vml122/hiring/)
- **申请数、锁帖、日期久远分别只是一种观察。** 结束判定仍按用户确认的规则，以需求方或有效来源标签的明确结束证据为准；失败请求只产生“无法核实”。

## 首版字段与删除规则的落地边界

以下为研究建议，尚未修改领域定义或业务决策：

| 产品要求 | 来源接入验收应检查什么 |
|---|---|
| 最近三天，用户可修改 | 保留原始发布时间、精度、首次发现时间和最近检查时间；Bluesky 搜索返回后须核对 `createdAt`，不能用索引时间替代原始时间。只有日级日期的边界处理另定。[时间过滤定义](https://raw.githubusercontent.com/bluesky-social/atproto/main/lexicons/app/bsky/feed/searchPosts.json) |
| 人民币参考预算 | 提取金额／区间、明确币种、总价／每张／时薪单位；币种未知不擅自兑换，未披露金额独立标记。汇率来源、时间、区间比较规则待规格明确。 |
| 每条需求显示接单状态 | 同时保存状态、检查时间、证据来源及证据作者身份；看不到私信成交，就只能说“未发现结束信息”。 |
| URL 存档排除 | 使用来源稳定 ID 辅助规范网址；去除追踪参数但保留帖子身份。新帖子命中结束记录才排除，不能过度合并不同需求。 |
| 删除详情，只留结束记录 | **“需求结束”和“作者删帖／来源要求删除”必须分别处理。** 前者是业务状态；后者可能要求连已存数据及派生信息一起删除。不能把删除请求当普通抓取失败，也不能假设永久 URL 或 URL 哈希天然豁免。来源许可需单独确认最小记录能否保留。[Reddit 条款](https://redditinc.com/policies/developer-terms)、[Bluesky 删除要求](https://bsky.network/docs/developer-guidelines/)、[X 政策](https://docs.x.com/developer-terms/policy) |

## 下一步可执行的小验证

优先解决一条来源的许可和可访问性，再在一个明确连续的 72 小时窗口做有界采样。记录实际发现量、买方比例、预算缺失比例和核验可见性；这些是观察数据，不新增用户必须达到的成功门槛。

对每一来源先通过：发现一条候选 → 取得原始时间与稳定 ID → 识别买方和预算 → 重读原帖／作者更新 → 正确处理明确结束或删除。人工抽查与 AI 分类的误判应分别记录，尤其是假招聘、机器人模板、供给广告和单位错误。本轮没有跑 AI 准确率评测。

请求规模可按“发现查询＋当天所有用户候选取并集后的核验”估算，避免同一条需求因多个订阅者重复检查。API、模型、邮件、服务器成本分开统计；未知报价保持未知。若以后试 X，帖子读取单价可以据实预算，但本轮未取得所需读取数量，不能给总成本承诺。[X 当前计费](https://docs.x.com/x-api/getting-started/pricing)

## 本轮完成范围

已核查官方文档、平台规则和八条历史买方原帖；对比五类来源；仅做一次 Bluesky 无登录、小量只读请求，返回 403 后停止。未批量抓取、未注册、未申请许可、未发送消息、未付费、未联系样本需求方。

Bluesky 测试由 shell 中 Python `urllib.request.urlopen` 发出无认证 GET，超时上限 20 秒，实际返回 `HTTP Error 403: Forbidden`，没有重试。请求为 `https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts`，参数：`q="looking to commission"`（含双引号）、`sort=latest`、`since=2026-09-15T02:59:00Z`、`until=2026-09-18T02:59:00Z`、`limit=10`。这是本环境单次观察，不是接口整体可用性的结论。

没有验证：最近三天真实供给量、持续运行稳定性、AI 精确率、需求方身份与支付能力、国内用户访问和申请成功率、第三方平台给本产品的最终授权。报告中的候选顺序是基于已查证据的建议，不是已经接通的来源清单。
