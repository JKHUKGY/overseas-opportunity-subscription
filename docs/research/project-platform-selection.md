# 首版自动采集实验：项目平台选择

核查日期：2026-09-22。依据[已确认需求](../discovery.md)与[领域术语](../../CONTEXT.md)：绘画接稿首发、个人委托优先，项目平台为主，自动采集是前提。本文是研究建议，不替用户更改决策。

后续决定（同日，第十三轮）：用户已选择 Freelancer 为首个实验对象，并要求扩展类似平台的调查；Upwork 后续获取路线改为浏览器读取、不使用 API。下文保留当时 API 路线的研究证据，不应将其理解为当前仍计划接入 Upwork API。用户要求保留中文总结，平台针对本产品的数据使用许可仍未验证；最新决定与浏览器实测结果见[业务探索记录](../discovery.md)。

## 结论

**有条件首选 Freelancer.com，使用官方 API 做小范围只读实验；Upwork 是取得专门合作授权后的备选。当前没有一个候选已被证明可以直接用于本产品的公开运营。**

选择 Freelancer 的理由不只是有接口：官方把帮助自由职业者寻找工作的 `Work Sourcer` 列为常见集成，提供项目搜索、详情重读、沙箱和个人访问令牌；原站也能找到头像、宠物肖像等个人绘画委托。该定位较贴合本项目。但官方同时禁止无附加价值的平台替代品，具体中文聚合、邮件和长期网址排除仍需确认。[官方集成类型](https://developers.freelancer.com/docs/api-overview/types-of-integrations)、[官方 SDK](https://github.com/freelancer/freelancer-sdk-python)

## 四个平台的取舍

| 平台 | 自动获取证据及当前前提 | 本轮排序 |
|---|---|---|
| Freelancer.com | 官方搜索/详情 API；本人探索可用个人令牌，沙箱与生产分开。生产采集、再展示和存储范围仍须与授权对应。 | **首选实验对象**，先解决用途和令牌，再验证真实读取。 |
| Upwork | 商业 API 仅向事先书面许可的精选合作伙伴开放。免费首版不自动排除商业用途；普通 API key 不等于本产品获准。现行 API & MCP 条款（2026-08-13 生效）对系统化提取、持续监控另有限制。 | **条件备选**；已有明确 API 路径，但不能假设六周内获批。[商业 API 说明](https://support.upwork.com/hc/en-us/articles/17995890765459--Commercial-API-use)、[现行条款 §3.5、§4.1](https://www.upwork.com/legal#apimcpterms) |
| Guru | 原站有雇主发布的插画项目；本轮没有找到可供本产品使用的官方公开买方搜索 API、授权流程或数据价格。 | 暂不作为自动采集首选；取得官方数据合作渠道后重评。`developer.getguru.com` 属于另一款知识库产品。[原站插画项目目录](https://www.guru.com/m/find/freelance-jobs/illustration/) |
| PeoplePerHour | 官方网站使用条款禁止 crawl/spider 和 harvest/scrape，商业使用内容需许可；本轮未查到官方公开项目搜索 API。 | 暂不采用网页爬取路线，只有获得明确供数许可才重评。[官方条款](https://www.peopleperhour.com/static/terms-of-website-use) |

“未找到 API”是此次检索结论，不是断言平台不存在私有合作接口。没有用第三方抓取服务或服务商广告充当官方许可。

## Freelancer 接入事实与限制

**认证。** 官方支持 OAuth2。只代表自己探索 API 时，文档指向 Personal Access Token，而非申请多用户客户端；令牌分别从生产/沙箱开发设置生成，文档称有效期 30 天。代其他用户操作的客户端需提交用途、权限等资料，官方预计通常五个工作日内回复，但不是获批保证。本次未登录或申请。**个人令牌仅解决认证，不自动授予本产品的采集/再展示许可；它与用户协议书面许可要求的关系仍应让平台确认。** [个人令牌](https://developers.freelancer.com/docs/authentication/personal-access-tokens)、[客户端申请](https://developers.freelancer.com/docs/authentication/creating-a-client)、[SDK 使用要求](https://github.com/freelancer/freelancer-sdk-python/blob/master/README.rst)

**读接口。** `GET /api/projects/0.1/projects/active/` 搜索开放候选，`GET /api/projects/0.1/projects/{id}/` 重读详情；SDK 的 `search_projects` 还支持 all 搜索。搜索接口文档要求 basic scope。不要请求私信、附件、付款或代投标权限。[官方项目文档](https://developers.freelancer.com/docs/projects/projects)、[SDK 实现](https://github.com/freelancer/freelancer-sdk-python/blob/master/freelancersdk/resources/projects/projects.py)

| 产品需要 | 官方证据与实现注意点 |
|---|---|
| 原始时间与稳定网址 | 官方示例有 `id`、`seo_url`、`submitdate`、`time_submitted` 和 `time_updated`；网址依 `seo_url` 构建，ID 辅助去重。**时间筛选参数不能直接代替原始发布时间检查**：文档部分 `from_time/to_time` 按最后更新过滤，须以返回的提交时间再检查三天窗口。[项目示例](https://developers.freelancer.com/docs/use-cases/bidding-on-a-project)、[项目查询文档](https://developers.freelancer.com/docs/projects/projects) |
| 人民币参考预算 | 用 `budget.minimum/maximum`、`currency.code`、`type` 区分总价与时薪；`bid_stats.bid_avg` 及网页 Average bid 是投标均价。示例中的 `min_avg_price` 也是均价过滤，不能拿来实现用户最低预算。[官方示例](https://developers.freelancer.com/docs/use-cases/bidding-on-a-project) |
| 接单状态 | 有 `status`、`frontend_project_status`，可请求 `selected_bids`。后者包含已授予或待定的投标，**非空不等于已接走**；须结合具体授予/接受状态、项目状态核验。`Closed` 可说明已结束，不能直接写成成交。[项目文档](https://developers.freelancer.com/docs/projects/projects)、[投标操作说明](https://developers.freelancer.com/docs/use-cases/performing-a-bid-action) |
| 国内画师是否可接 | 有国家、语言、地点和 local 等查询/项目信息，但不能据国家过滤器声称已确认接受中国画师。继续读需求限制；未说明则按既定规则标注“地域未说明”。[过滤器源码](https://github.com/freelancer/freelancer-sdk-python/blob/master/freelancersdk/resources/projects/helpers.py) |

这些是文档能力，**尚未以本项目的生产凭证验证字段覆盖率或可见性**。官方文档中的老示例不能证明当前接口稳定。

**授权是主要前提。** 用户协议 §33 涵盖自动访问（明确包括 API），并要求相应书面许可；站外复制、衍生和展示另有许可要求。API 条款 §5 将缓存限定为性能用途、至少每 24 小时刷新，限制其他存储及派生数据，要求加密；终止后还有删除义务。因此每日刷新不等于允许长期机会库，URL/哈希也不是天然豁免。[用户协议](https://www.freelancer.com/about/terms)、[API 条款](https://www.freelancer.com/about/apiterms)

接入前需让平台确认：自动发现公共项目；AI 中文摘要及所用处理方；本站展示和邮件摘要；缓存范围与刷新；结束后仅留网址、来源、时间、原因；来源要求删除时同步清理。现有“允许按来源要求删除存档”规则只解决删除动作，**不能代替最初的存储授权**。这是对本产品的适配判断，尚无平台针对本产品的批准回复。

**费用和限额。** 未在所查官方文档取得本用途的 API/数据授权报价，不能承诺免费，也不能把交易抽成当读取接口费用。限流按端点和响应头确定，429 时退避；文档里的 50/分钟、1000/小时只是示例，不能当本账户配额。[限流说明](https://developers.freelancer.com/docs/api-overview/rate-limiting)

## 四条真实绘画买方样本

均为原站公开项目页的本轮取样，不转载个人联系方式。不将投标人数、更新时间或分类页标题当发布时间；页面快照可能滞后。

| 原帖与 ID | 买方预算/需求 | 时间与状态证据 |
|---|---|---|
| [Roblox 角色头像](https://www.freelancer.com/projects/digital-art/cartoonish-roblox-avatar-portrait)，40724974 | £10–20 GBP，总价；为自己的游戏形象绘制卡通头像 | 本次取得页面显示“Posted 1 minute ago / Open”，属于近期候选；只有相对时间，未取得可核验绝对时间戳，不能据此量化整个 72 小时供给。 |
| [手绘宠物卡通](https://www.freelancer.com/projects/2d-drawing/realistic-hand-drawn-pet-cartoon)，40520948 | £250–750 GBP，总价；为自己的宠物绘画 | 取得的搜索快照显示八天前、Closed；历史/窗口外样本，绝对发布时间未确认；关闭原因未知。 |
| [猫咪与玩具肖像](https://www.freelancer.com/projects/digital-art/realistic-pet-portrait)，40574417 | $30–250 USD，总价；自己的猫及玩具 | 同一次研究的搜索/打开快照分别显示约一月前、七天前，均为 Closed。时间不一致，不能判定为近三天机会。 |
| [四只狗的桌面壁纸画像](https://www.freelancer.com/projects/illustration/need-illustrator-graphic-artist-for)，29864411 | $40–100 USD，总价；自家四只狗的卡通画 | 页面显示约五年前、Completed；仅作历史已结束样本，不能推送。 |

四条均未在所取正文中看到排除中国承接者的明确要求；“Remote”也不等于已确认全球可接。样本证明平台有个人委托，不证明真实性、付款能力或每日数量。[插画目录](https://www.freelancer.com/jobs/illustration/)还混有竞赛、标识设计和其他任务，实验建议先排除竞赛，单独统计个人委托比例。

## 下一步可执行的只读实验

以下是建议的工程验收，不新增商业成功门槛，也没有在本轮启动：

1. **用途与凭证准备**：记录官方允许的读取、摘要、保留、展示范围及报价；本人实验按官方开发设置取得相应环境令牌。当前无凭证、无本用途批准，不提交自动申请或消息。沙箱只验证调用格式，不能证明真实需求供给。[沙箱](https://developers.freelancer.com/docs/api-overview/sandbox-environment)、[开发设置](https://accounts.freelancer.com/settings/develop)
2. **单次最小搜索**：在获准环境用 SDK `search_projects(session, query='portrait', active_only=True, limit=10)`，再对一个返回 ID 执行 `get_project_by_id`；只请求正文、技能和必要状态。记录 HTTP、请求 ID、限流头、实际字段/缺失值；遇 401/403 停止查权限，429 依限制退避。不得改用爬虫绕过。[搜索例](https://github.com/freelancer/freelancer-sdk-python/blob/master/examples/search_projects.py)、[详情例](https://github.com/freelancer/freelancer-sdk-python/blob/master/examples/get_projects.py)
3. **连续 72 小时有界取样**：在获准配额内，建议每六小时按 illustration、portrait、character 三组词/技能查一页，每页最多 20 条，再对去重候选核验详情；未完整翻页则报告“样本量”，不声称总供给。按源 ID 去重，并按原始提交时间过滤。取样语种与关键词会影响覆盖率，应明确记录。
4. **保存验收数据**：发现数、明确付费买方数、个人委托数、三天内数、预算/时间/状态缺失比例、实际请求量与费用；抽查至少十条或全部不足十条样本，对比原帖与提取结果。核验 open/closed/awarded/pending 的区别，401/403/打不开不能判已接走。
5. **结束记录流程**：在允许的范围内测试先写独立结束记录再删详情、再次遇同网址排除，以及来源删除要求清理记录。没有授权时用合成数据测试，不长期保留真实关闭项目详情。最终只把测得的字段与授权约束带入规格。

当前先选 Freelancer 争取接入并验证；若用途被拒或关键字段不可读，切换到具备匹配授权的 Upwork；两者都未获准时，结论应是“自动来源前提未满足”，不是默认开始网站或转成人工录入。

## 研究边界与可复核性

本轮阅读官方页面、API 文档与官方 SDK，取得四条原站样本；未注册、购买、申请权限、发送消息或调用生产项目 API，未跑 AI 准确率及 72 小时实验。搜索结果含缓存，近期数量仍未知。

头像样本在本轮后续复核时，网页读取工具未能再次打开；前面的预算与相对时间来自首次取得的页面，不能据此声称持续可访问，也不能把读取失败判为需求结束。

Freelancer 开发站是 JavaScript 页面，普通网页读取器未展开正文；本轮从其首页明确引用的[官方文档静态资源](https://developers.freelancer.com/static/js/main.8e27893a.js)读取相应文档内容，不涉及私有业务接口。临时核查摘录放在项目 `temp/freelancer-official-doc-excerpts.txt`，报告的持久引用为上面的官方文档链接。
