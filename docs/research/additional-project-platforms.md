# Freelancer / Upwork 以外的项目平台

核查日期：2026-09-22。接续[首次平台选择研究](project-platform-selection.md)。用户已选择 Freelancer 作为首个实验对象，要求继续寻找同类来源，并探索 Upwork 浏览器路线。本报告只调查其他平台；不声称已执行浏览器持续采集。

后续范围补充：用户明确将 VGen 加入当前绘画接稿领域的来源测试。此为已确认测试范围，不表示已证明它能提供公开买方项目；专项复核见 [VGen 来源检查](vgen-source-check.md)。

## 建议

**新增候选优先看 Workana 和 PeoplePerHour，Guru 与 Truelancer 放第二组。** 四者都有需求方发布的项目，不只是画师服务广告。这个顺序按本轮找到的绘画项目和字段可见性提出，属于下一轮浏览器小样本测试建议；尚未测得各站最近三天的供给数量，也未证明个人委托占比。

| 平台 | 与绘画接稿的匹配 | 公开读取与接入证据 | 建议 |
|---|---|---|---|
| **Workana** | 找到儿童书插画、出版插画、矢量艺术买方项目；样本同时有英文、西班牙文、葡萄牙文。 | 未登录的官网详情搜索快照可见正文、绝对发布日期、项目分类及活动信息。列表阅读器本次只展开标题和注册提示；不能由此断言必须登录。 | **优先新增测试**：先验证列表能否展开、预算是否可见，再核实原始时间和项目状态。 |
| **PeoplePerHour** | 儿童书、传统插画、艺术品等买方分类与详细需求；样本包含个人作者约稿。 | 详情快照包含价格、固定价/时薪、Remote、ID、提案数，以及 Open for Proposals / Awarded / Completed / Expired 状态。直接打开列表时出现机器人验证，本轮未继续绕过。申请页明确要求登录。 | **优先新增测试**：英文机会与状态字段较贴合；浏览器访问稳定性未知。 |
| **Guru** | 插画目录有作者找画师、网站插画，也混入动画、营销、助理等非约稿项目。 | 搜索快照可见预算档、月日及申请截止日；直开目录返回 403。快照未给年份，不能推算最近三天。 | 第二组；先验证详情读取和时间精度，不按“插画”目录全收。 |
| **Truelancer** | 找到线稿、书籍、水彩角色项目。 | 列表本次可读，有相对时间、价格类型、金额、提案数；详情第一次返回页面索引，但复开为 403。目录快照之间时间和金额不一致。 | 第二组；先解决数据一致性，并抽查正文是否真为约稿。 |

目录来源：[Workana](https://www.workana.com/en/jobs?skills=illustration)、[PeoplePerHour](https://www.peopleperhour.com/freelance-illustrator-jobs)、[Guru](https://www.guru.com/m/find/freelance-jobs/illustration/)、[Truelancer](https://www.truelancer.com/illustration-freelancer-job)。

## 买方样本与字段问题

以下为原站页面或其搜索快照，**均不作为当前可推送机会**。没有取得可靠的最近三天证据，不把搜索引擎抓取时间视为原始发布时间。

### Workana：双语儿童读物插画

[Experienced Children's Book Illustrator for Bilingual Educational Content](https://www.workana.com/job/experienced-childrens-book-illustrator-for-bilingual-educational-content)：原始发布日期显示 **2026-06-14**，找画师绘制儿童健康生活习惯的双语读物，要求 Latino 角色。样本要求的是角色形象，不能误读成画师必须来自拉美。后续复核取得的页面顶部为 In progress，正文区域另有 Open，不能判作仍开放招人。页面显示投标活动、付款方式已验证，但未展开可核验数字预算；应标记预算未说明，不能根据付款验证标记推测预算或项目真实性。

另有[西语出版插画项目](https://www.workana.com/job/disenador-grafico-e-ilustrador-para-proyecto-editorial-de-libro)，发布日期 **2026-03-24**，正文明确远程和按项目合作。它说明非英语机会值得试验，但中文摘要不能替代画师后续沟通能力。

**状态陷阱：** [另一条已完成项目](https://www.workana.com/en/job/diseno-y-maquetacion-de-catalogo-de-productos-para-hosteleria-en-adobe-illustrator)的快照同时出现页面顶部 Completed 与 About this project 下的 Open。后者可能是展开正文控件或模板文字，不能看到一个 Open 就判定仍在招人。实现需以实际状态组件核验。

### PeoplePerHour：儿童书插画

[Children's book illustration #4492742](https://www.peopleperhour.com/freelance-jobs/design/illustration-drawing/children-s-book-illustration-4492742)：快照显示 **£20 固定价、Remote、Open for Proposals、13 个提案**，需求是按提供的想法制作插画并交付高分辨率文件。快照为约四个月前抓取，所写“4 days ago”不代表今天四天前发布；当前状态未重新确认。

[另一条个人作者的儿童书项目 #2784788](https://www.peopleperhour.com/freelance-jobs/children-s-book-illustration-2784788)明确为自己写的童话找插画师，原币种 **$100**，页面另给英镑近似值，状态 Completed，属于历史已结束样本。产品应保留原币种而不是将页面近似英镑当原始报价。

### Guru：作者寻找书籍画师

[官网插画目录](https://www.guru.com/m/find/freelance-jobs/illustration/)中 **Illustrator for Alternative....**，摘要说明作者寻找高质量绘画，固定价 **Under $250**，显示 Posted Jul 4 / Send before Oct 31，但没有年份和可核验的结束状态。[官方标题索引](https://www.guru.com/sitemap/jobs-by-title/)给出项目 ID **2119231**。本轮未读到完整详情，因此只能确认绘画买方候选，不能确认仍可申请或中国画师资格。

同目录的 **MAGAZINE Illustrator/Graphics- S.AMERICA** 明确要求南美承接者，应按既定地域规则排除。另有项目要求不用 AI 作画，此处是交付要求，不能与平台生成中文摘要混为一谈。

### Truelancer：线稿画师

[Need a Freelance line illustration artist #617097](https://www.truelancer.com/freelance-project/need-a-freelance-line-illustration-artist-617097)：[插画目录](https://www.truelancer.com/illustration-freelancer-job)快照给出 **固定价 $44、15 个提案、a day ago**；另一份[艺术工作目录](https://www.truelancer.com/freelance-artist-freelancer-job)快照为 **$42、27 个提案、6 months ago**。没有证据确定差异来自换汇、更新还是缓存，故不能将这条作为近期供给或可靠原币种金额。正文提取未完成，供给匹配仍需人工抽查。

目录也出现 **Location Specific**，如仅印度或特定城市承接者可申请。地域条件必须逐条读取；平台面向多国不等于每个项目都接受中国画师。

## 接口、登录与中国画师适配

- 本轮官网定向检索和公开入口中，**四个平台均未找到可核验的官方公开买方项目搜索 API 文档与接入流程**。这是研究未证实，不是断言没有私有或合作接口。API 开发服务广告、开发者简历和第三方抓取服务不算平台 API。尤其 `developer.getguru.com` 是另一款知识库产品，不应当成 Guru.com 市场接口。
- Workana 官方说明注册后建档、选项目、与需求方交流；PeoplePerHour 接单者需验证邮箱并提交申请资料。公开浏览与有资格申请是两件事。[Workana 接单流程](https://www.workana.com/work/freelancers)、[PeoplePerHour 申请流程](https://support.peopleperhour.com/hc/en-us/articles/4408655983633-Freelancer-Application-Process)
- 本轮未以中国账号完成四站注册、身份核验、投标或收款验证。不能向画师保证全部可注册、可申请或可提现。未写地域条件的机会继续按“地域未说明”处理。
- 浏览器能够显示页面与长期自动监控是两项不同验证。PeoplePerHour 当前公布的网站条款限制抓取与商业内容使用；相关范围单独记录，不将它混同为“没有绘画需求”。本轮没有进行绕过验证、批量提取或公开发布。[网站条款](https://www.peopleperhour.com/static/terms-of-website-use)

## 不优先作为公开买方池的平台

**Fiverr**：官方 Briefs 流程是将买方需求匹配给少数合适自由职业者，经账户、邮件或 App 通知；不能把画师服务目录当成全量公开机会列表。[官方 Briefs 说明](https://help.fiverr.com/hc/en-us/articles/4415608857745-Personalized-offers-Briefs-for-freelancers)

**Malt**：官方流程以客户搜索自由职业者或算法匹配，再向选中的自由职业者发送项目为主；本轮未确认公开绘画买方列表，因此暂不优先。[官方匹配说明](https://help.malt.com/hc/en-150/articles/29580121135634-How-do-I-find-the-right-freelancer-for-my-project)

## 下一轮有界实验

保留 Freelancer 为首个实验。新增来源先各检查 Workana、PeoplePerHour 一个插画列表和最多五条详情，记录：是否需登录、是否有稳定 ID、原始发布时间、原币种预算及价格单位、真实结束状态、地域要求、个人委托/商用项目分类。只有正常可见的页面才进入摘要测试；机器人验证和无法加载记为读取失败，不能记为已结束。

浏览器样本验证成功后，再比较同一 72 小时窗口的新增项目数和可用字段比例，决定扩展哪个来源。本轮没有执行这项实验，也没有对任一平台的持续自动化成功率作出承诺。
