# 海外个人绘画约稿来源：首轮事实核查

核查日期：2026-09-18。范围：最多三个候选来源的公开一手页面；未登录、未申请接口、未联系任何人、未进行批量采集。本报告支持后续复用，不是机会数量或转化率调查。

## 结论

- **Reddit / HungryArtists 是本轮最明确的买方需求候选**：社区官方指南区分 `[Hiring]` 与 `[For Hire]`，前者要求预算。存在官方数据 API，但面向本产品的商业获取和使用不能视为已获许可，需要另行协议。[社区指南](https://www.reddit.com/r/HungryArtists/wiki/client/)；[API 条款](https://redditinc.com/policies/data-api-terms)
- **VGen 不能直接当作公开买方需求池**：已核实的官方流程从画师服务菜单开始，需求方向特定画师提交委托。官方条款明确限制爬取、系统收集并编成数据库。[委托流程](https://help.vgen.co/hc/en-us/articles/12820045188119-How-does-the-VGen-commission-system-work)；[服务条款第 5 节](https://vgen.co/terms-of-service)
- **Artists&Clients 暂列未知**：本轮能获得的是画师出售服务的页面；买方公开需求列表、官方批量接口、商业聚合许可均未核实。不能把检索到大量画师服务当作大量约稿机会。[服务页面样例](https://artistsnclients.com/slots/104063-half-body)

## 1. Reddit：HungryArtists（artcommissions 尚待补充）

**事实**：HungryArtists 自有 Wiki 指导需求方使用 `[Hiring]` 标题、写明预算和货币；`[For Hire]` 是画师供给帖。指南有 DnD 团队绘画、家人肖像等示例，但这些示例不是当前可申请订单。社区称自己是国际社区。[需求方指南](https://www.reddit.com/r/HungryArtists/wiki/client/)

**事实**：Reddit 有官方 API 文档，包含列表、分页等能力。商业用途需要单独协议；条款还限制超出获批用途的数据保留及未经书面批准的收益性使用。是否批准本产品、费用、可保存字段、第三方 AI 分类与摘要、再展示方式均未核实。[官方 API 文档](https://www.reddit.com/dev/api/)；[Data API Terms 第 2、3 节](https://redditinc.com/policies/data-api-terms)；[官方访问说明](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Reddit-Developer-Interfaces)

**推断**：`[Hiring]` 可用于候选发现，但仍应复核正文是否明确付费、是否已关闭、是否属于绘画、是否为个人委托；不能仅凭标签保证真实性。`[For Hire]` 应排除。

**未知**：本轮未获得足够的 artcommissions 规则正文，因此不将 HungryArtists 的具体标签、预算规则自动套用到该社区。没有测量日供给量、有效期或中国画师成功率。

## 2. VGen

2026-09-22 后续决定：用户已明确将 VGen 纳入绘画接稿领域的来源测试，下文暂不纳入的建议不再代表当前测试范围；公开买方需求入口仍需复核。

**事实**：官方帮助文档描述 Custom Proposal 和 Instant Orders，两者均围绕画师预先设置的服务；前者由需求方向画师提交请求，后者直接购买服务。本轮没有找到可供第三方聚合的公开买方需求目录或官方公开批量需求 API。[委托流程](https://help.vgen.co/hc/en-us/articles/12820045188119-How-does-the-VGen-commission-system-work)

**事实**：服务条款第 5 节列出对爬取、未经允许复制存储、系统检索并编成数据库的限制，不能据网页公开可访问便推定可以商用采集。[服务条款](https://vgen.co/terms-of-service)

**事实**：官方支持国家页面列出 China，且放在 PayPal Only 表中。这只是平台画师收款支持范围，不能证明每位需求方愿意向中国画师约稿，也不等于任何个体账户一定通过支付服务审核。[支持国家](https://help.vgen.co/hc/en-us/articles/40469294324503-Which-countries-does-VGen-support)

**推断**：VGen 更适合作为理解画师服务分类与交易流程的参照；在没有额外明确证据或许可前，不列为首版自动采集源。

## 3. Artists&Clients

**事实**：可检索到的站内服务页面带有画师用户名、基础售价、绘画范围和联系画师入口；这是画师出售服务的信息。[页面样例](https://artistsnclients.com/slots/104063-half-body)

**核查限制**：本轮尝试打开候选 `/jobs` 与 `/terms` 地址失败；这些地址未被证实是有效入口。搜索未找到足以核实公开买方需求列表、平台官方 API 或商业聚合条件的页面。不能据此断言相关功能不存在。

**判断**：保持候选状态；在补齐官方证据前，不纳入已确认的需求来源。

## 地域资格与当前领域定义

研究时 `CONTEXT.md` 的“可推送机会”要求明确接受订阅者所在地远程承接。**帖子未写地域限制，并不能推出接受全球或中国画师**；国际社区、英文帖子、数字交付、平台支持中国收款，都不是某个需求方接受中国承接者的充分证据。

建议保留“明确符合／明确不符／未披露”三态，并保存判断依据。本报告没有测量地域规则会排除多少机会。后续访谈 Q25 中，用户已明确允许地域未披露的机会收录和订阅，标注“地域未说明”，明确不符的机会仍排除；最新产品规则见 [业务探索记录](../discovery.md) 和 [CONTEXT.md](../../CONTEXT.md)。

## 尚未回答的问题

1. 按最新地域规则，每周究竟有多少可推送机会？需要在可用来源和使用方式明确后进行有界取样。
2. Reddit 是否批准该聚合场景，以及 AI 摘要、保留期限、删除同步、商业展示的具体条件？
3. 首轮是否覆盖实体画作、成人委托与其他特殊内容，以及如何区分作品类型和风格？这些是产品范围决策，本轮未替用户决定。

上述建议是根据官方页面与项目定义作出的产品推断；“未知”项不能写成已经验证的能力或事实。
