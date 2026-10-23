"""PROTOTYPE: transform this one-off browser snapshot; no network calls."""
import json
from pathlib import Path
from datetime import datetime
from collections import Counter

ROOT = Path(__file__).resolve().parent
raw = json.loads((ROOT / 'source-facts.json').read_text())
annotations = '''
662148|嵌入式与物联网|开发 GPS 同步的赛车计时设备，包含传感器检测、PCB、固件和可工作的原型，目标为微秒级计时。
661026|AI 与自动化|用 Just247Pipes 构建 AI 代理与业务流水线，连接邮件、数据库和 API；先做一周付费试验，再按里程碑交付。
661635|嵌入式与物联网|开发、调试并烧录 STM32G031 固件，涉及传感器与电源控制；完整规格和电路图需签署保密协议后提供。
660311|游戏开发|用 Roblox Luau 制作模拟器游戏，包括地图区域和各项游戏系统；详细需求在未读取的附件中。
659450|数据与脚本|编写 Excel VBA 宏，自动化表格操作与任务流程；原帖称用于一项作业，具体业务细节较少。
657914|数据与脚本|用 Python 开发股票波段交易系统，包含策略回测、风险控制、结果看板和 Zerodha Kite 集成。
657805|工业控制|编写 Delta PLC 与 HMI 程序，赴现场上传、测试与调试；需有实际工业控制经验。
657521|AI 与自动化|开发求职流程工具，导入职位、分析匹配程度、整理申请材料，并提供用户审核和进度跟踪功能。
657062|AI 与自动化|开发面向客服、文档处理和业务流程的 AI 机器人，涉及 RAG、API、Python 或 JavaScript 及自动化平台。
656850|工业控制|编写、排查和维护 Allen Bradley PLC 程序；公开描述简短，具体控制设备和交付范围需确认。
655698|网站与后端|按项目参与远程软件开发，要求独立解决问题、沟通协作，并掌握至少一种编程语言；具体项目细节待面谈。
655913|工业控制|开发 Siemens PLC 自动化方案与 HMI 界面，完成控制系统集成，需要实际 PLC 调试经验。
655203|企业系统|参与 SAP ABAP 项目开发与复杂调试，覆盖 RICEFW 报表、接口、转换、增强、表单与工作流。
653011|AI 与自动化|设计多代理系统，开发代理通信、协调与决策机制，完成 AI 集成、性能测试和系统优化。
650968|数据与脚本|协助 SketchUp 编程相关项目，同时需要 3D 建模技能；公开需求较短，具体功能未展开。
650726|工业控制|修改既有 Allen Bradley CompactLogix PLC 逻辑和 HMI 界面，适应新的运行要求并进行优化。
649361|测试与评审|评估 AI 模型执行真实软件工程任务的行为，比较代码工作流、工具使用和验证过程，按规范撰写评估。
649154|游戏开发|用 Panda3D、Python 和 C++ 开发与调试 3D 游戏仿真环境，用于 AI 训练；原帖标明远程合同工作。
644813|网站与后端|寻找熟悉现代 C++、并发、数据结构、图算法和 REST API 的后端开发者；具体交付范围需进一步确认。
644005|AI 与自动化|将 ChatGPT 对话能力集成到业务项目，定制响应、接入 API，完成测试、优化和交付文档。
643004|应用开发|用 Python 开发带图形界面的计算器，支持基本四则运算，需要熟悉 GUI 框架。
642923|数据与脚本|用 Streamlit 制作天气分析看板，接入 OpenWeather API，保存历史数据并展示交互图表与城市对比。
642709|企业系统|支持 SAP SuccessFactors、EC 到 ECP 的复制集成，进行 ABAP 开发、调试和增强，初期为兼职合同支持。
642170|应用开发|使用 Flutter 开发和维护出租车应用，接入 API 与支付，处理测试、性能和发布；外部规格链接未访问。
639336|嵌入式与物联网|开发 672 钩电子提花控制系统，包括模块映射、实时同步、传感器接口与电磁驱动控制，先做付费原型。
638909|网站与后端|修复 Python 房地产分析 SaaS 的数据同步、云端定时任务和 Stripe 支付问题，并协助部署和验证。
637338|应用开发|排查 Kotlin 安卓图书馆应用中的界面崩溃问题；平台显示 Active & Freezed，申请可用性需核实。
635614|嵌入式与物联网|搭建红外传感器与 Arduino 实验系统，编写检测和输出代码，完成接线、测试与简单数据记录。
632831|嵌入式与物联网|设计、编程并测试定制电子调速器 ESC，完成适配特定需求的控制方案。
632380|数据与脚本|融合 GPS 与 IMU 数据，开发实时车辆路径估计模块，实现传感器滤波与稳定的轨迹输出。
631681|嵌入式与物联网|基于 ESP32 开发类似投影键盘的简易 AR 设备，包含硬件集成与固件开发。
631385|数据与脚本|改进 Python 实时加密货币交易系统，增加功能并优化实时处理、可靠性与扩展能力。
631101|嵌入式与物联网|为工业和医疗产品开发嵌入式硬件及固件，按具体项目要求优化系统功能。
630457|工业控制|将新的电力监测仪表接入 Siemens S7-400H 冗余 PLC 系统，处理硬件配置、通信模块和现场集成。
630189|应用开发|开发 ASP.NET 网站应用及 Android、iOS 移动应用；项目具体功能和里程碑尚未详细披露。
629561|数据与脚本|用 Python 和 Whitebox Tools 自动处理百万点 LiDAR 数据，提取地物、计算天空可视因子并输出 KML。
629571|数据与脚本|实现 ANN 回归与 NSGA-II 多目标优化脚本及 GUI，用于复现研究结果，包含训练、验证和参数优化。
628529|数据与脚本|编写 Python 交易策略脚本并连接 Futu API，实现期货交易自动化；原文要求人在香港。
628258|游戏开发|设计并实现一款 RPG 游戏及其机制；原帖点名希望由 William 承接，开放招募程度需确认。
627518|企业系统|为安保公司开发工资管理系统，涵盖考勤、薪资、扣税、奖金、权限控制及报表导出。
627215|企业系统|定制和优化 Odoo SH V19 会计模块，整合工作流并提供故障排查与后续技术支持。
626837|AI 与自动化|用开源技术构建实时全身 AI 数字人直播系统，输入照片和脚本，生成带动作与口型同步的视频流。
626774|网站与后端|开发车队管理平台的管理看板与司机应用，技术栈包括 Python、FastAPI、PostgreSQL 和 Angular。
625444|工业控制|用 Siemens TIA Portal 编写工业清洗线控制程序，处理篮筐传送、工序顺序、互锁和异常恢复。
625486|AI 与自动化|利用 n8n、Zapier、Make 等搭建业务自动化，连接多应用 API、聊天机器人和 AI 语音助手。
625451|企业系统|使用 Microsoft Access 设计定制数据库，并通过 VBA 实现业务功能和易用界面。
624662|嵌入式与物联网|为玩具无人机的集成电路编写控制程序；芯片资料和详细规格将提供给选定的承接者。
624130|嵌入式与物联网|为 PAN2416AV 发射芯片和 PAN7420S7FA 接收芯片编写定制固件，用于玩具无人机。
622337|嵌入式与物联网|开发 ESP32 物联网固件，连接传感器与云平台，实现无线通信、OTA 更新和低功耗优化。
621796|数据与脚本|修复既有 Python 交易机器人中的错误，优化代码并提升运行稳定性。
621480|数据与脚本|使用 MQL5 开发 MT5 交易 EA 和指标，包含数学模型、自动策略及风险管理逻辑。
621294|嵌入式与物联网|为智能戒指等可穿戴设备开发硬件与低功耗固件，整合健康传感器、通信与安全功能。
621203|网站与后端|开发网站与应用，指定 TypeScript、Next.js、NestJS、Prisma/MongoDB 和 React Native 技术栈。
620274|企业系统|开发 SAP PO 接口、BTP 集成与 RAP/ABAP 功能，维护 CDS/OData 并调试系统增强逻辑。
617050|游戏开发|为 Unreal Engine 5 建筑可视化项目编写导航与信息菜单，适配 VR 和 Windows，整合现有设计。
616470|嵌入式与物联网|为已完成硬件的 ATMEGA328P 产品编写程序，控制数码显示、键盘、泵输出和压力输入。
616390|网站与后端|从头开发活动管理网站，包含活动检索、报名、组织者后台、Stripe 支付及 SEO 支持。
616078|嵌入式与物联网|基于 ESP32 制作 AI 语音助手原型，连接麦克风和扬声器，实现语音识别、音频响应及设备控制。
614974|网站与后端|开发和扩展 Python FastAPI 后端，处理异步任务、MongoDB 查询、JWT/OAuth 和 Celery。
614285|网站与后端|重新设计并开发获客落地页，优化表单交互和转化流程，要求提供相关网站开发案例。
613677|测试与评审|编写与维护 Cypress、Playwright 等自动化测试，覆盖接口、网页和移动应用，并结合容器及云环境运行。
613494|嵌入式与物联网|整合多个控制 PCB，升级现有软件的数据采集与报表，统一设备间 C++ 通信控制逻辑。
613358|测试与评审|用 Java、REST Assured 和 Postman 设计接口测试用例与自动化脚本，验证 API 的可靠性。
613294|工业控制|完善 Siemens 与 Delta 控制板之间的通信和控制算法，用传感器数据模拟电池 BMS 与混合逆变器。
610383|应用开发|负责 macOS 桌面应用的设计、开发、测试和维护，要求 React、Node.js，TypeScript 加分；预算描述不一致。
608274|游戏开发|远程参与 Unity 游戏开发，需编程或动画经验，每周工作 2–3 天；正文注明每月 $425，币种代码未披露。
607470|企业系统|参与 SAP ABAP、BTP 与 RAP 开发工作；公开描述较短，具体项目交付内容需要确认。
607305|游戏开发|用 Unity 3D 开发十关战斗游戏，包含车辆、武器、AI、场景和任务系统。
605546|工业控制|为 PTZ 摄像机项目编写 GL10 PLC 程序，建立与 Raspberry Pi 4 和伺服驱动的通信。
599099|网站与后端|以合同形式开发 React/TypeScript 前端，连接 Socket 和 REST 服务，并协助云架构与数据库工作。
598505|工业控制|为锅炉项目编写 PLC 程序，预计持续 1–2 个月，优先指定印度南部地区的候选人。
597591|应用开发|根据已完成的 UI 开发社交聊天应用，包含后端、功能联调、双平台测试、应用商店发布和源码交付。
592485|数据与脚本|使用 R/RStudio 完成金融计量与时间序列分析，从公开数据集中选择数据并实现指定模型；任务细节在附件中。
591770|数据与脚本|构建产品分析的数据架构、数据模型和可视化，处理管道质量、数据治理和大规模数据需求。
591096|嵌入式与物联网|开发带机械臂的半自主移动机器人，实现抓取、放置和路径导航；详细规则将在接受项目后提供。
589084|网站与后端|用 Python、SQLAlchemy、Django/Flask 和 AWS Lambda 开发后端 API 与微服务。
586506|网站与后端|定制 Shopify 模板与功能，将设计稿转成可用页面，改进既有网站并集成第三方应用；仅印度承接者。
581316|网站与后端|排查网站运行 npm start 时出现的启动错误，使原有项目恢复运行；外部代码压缩包未下载。
578876|应用开发|用 Kotlin 与 Spring Boot 开发活动购票安卓应用，包含活动检索、选票、账户、支付和电子票管理。
578332|企业系统|使用 SAP ABAP 开发定制接口，需要接口编程与数据库经验；平台限定俄罗斯联邦承接者。
578011|嵌入式与物联网|开发 STM32 摩托车自适应转向阻尼固件，采集传感器信号并实现实时闭环控制。
577672|嵌入式与物联网|组装并编写 Arduino 垃圾分拣系统程序，整合步进电机、舵机、接近传感器与雨水传感器。
576238|网站与后端|为多个电商网站项目提供前后端开发与维护，涉及 Shopify、Magento、WooCommerce 和数据库。
576062|嵌入式与物联网|为 ESP32 四旋翼玩具编写飞控，首先实现基于 IMU 和 PID 的稳定悬停与指令控制。
575894|测试与评审|使用 Java、Selenium 和 Postman 构建自动化测试框架，执行用例并分析前后端测试结果。
575691|网站与后端|优化线索管理应用的邮件地址验证接口，从每批 100 条扩展到数千条，涉及 Python、Django、Angular 和数据库。
575688|工业控制|协助开发 Siemens 水箱自动化 PLC 与 HMI，完善液位、阀门、定时器、告警及功能块逻辑。
574379|嵌入式与物联网|开发用于医疗应用的嵌入式控制系统，需要有电路与嵌入式系统开发经验。
'''
annot = {p[0]: {'category':p[1], 'summary_zh':p[2]} for line in annotations.strip().splitlines() if (p := line.split('|',2))}
exclusions = {
 '636150':'平台状态为 Freezed and Awarded（已授予）',
 '589272':'平台状态为 Freezed and Awarded（已授予）',
 '587758':'平台状态为 Freezed and Awarded（已授予）',
 '582424':'平台状态为 Freezed and Awarded（已授予）',
 '643877':'正文截止日期为 2026-05-30，已经过去',
 '576752':'本次读取未取得公开详情正文，不能凭列表补成完整记录',
 '642328':'正文描述一个已完成的待办应用，未确认买方开发需求',
 '599963':'正文使用已完成工作履历表述，未确认具体买方需求',
 '573779':'正文为通用安卓岗位描述模板，缺乏具体项目需求',
 '606766':'以 CAM 机械加工路径文件为交付，未纳入本次软件/固件开发范围',
 '574604':'以数控机械加工程序为交付，未纳入本次软件/固件开发范围',
 '589453':'正文要求发布当周周五交付，时间窗口已过',
}
regions = {
 '661635':('restricted','印度 Bangalore；需在当地实验室工作'),
 '657914':('restricted','平台限定 India（印度）'),
 '657805':('restricted','平台限定印度；需赴 Mumbai 或 Pune 现场，标题另提 Hyderabad'),
 '655698':('specified','远程；原文列出亚洲、欧美、澳洲、中东等多个地区'),
 '635614':('preferred','优先印度 Hyderabad，可提供线下帮助者'),
 '630457':('onsite','涉及 FM07-FTZ East & West 现场集成，所在国家未明确'),
 '628529':('restricted','原文要求位于 Hong Kong（香港）'),
 '598505':('preferred','优先印度 Tamil Nadu、Karnataka 或 Andhra Pradesh'),
 '586506':('restricted','标题明确 Only India（仅印度）'),
 '578332':('restricted','平台限定 Russian Federation（俄罗斯联邦）'),
}
notes = {
 '635614':['正文另写 ₹500–₹2000，和页面时薪卡片口径不同；未做换算。'],
 '610383':['正文同时写每月 $8,000、每月至少 40 小时及 $80/hr，和预算卡片口径不同且内部不一致；需向来源确认。'],
 '608274':['页面为固定价，正文却写每月 $425；保留两种原始口径。'],
 '628258':['原帖点名 William，可能不是开放招募。'],
 '637338':['平台显示冻结状态，不能视为当前可申请。'],
 '642170':['正文含外部规格链接，本轮未访问。'],
 '581316':['正文含外部代码下载链接，本轮未访问或执行。'],
}
rows, rejected = [], []
for r in raw['records']:
    if r['id'] in exclusions:
        rejected.append({k:r[k] for k in ['id','title','url','source_status','observed_at']} | {'reason':exclusions[r['id']]})
        continue
    assert r['id'] in annot, r['id']
    dt = datetime.fromtimestamp(int(r['published']['datetime'])/1000).astimezone()
    iso = datetime.fromisoformat(r['published']['title'])
    assert dt.timestamp() == iso.timestamp(), r['id']
    symbol = r['budget_raw'][0]
    reg = regions.get(r['id'],('unspecified','地域未说明；不代表已确认接受任意地区'))
    row = dict(r, **annot[r['id']], source='Truelancer',
               published_at=iso.isoformat(), currency_symbol=symbol,
               currency_code='INR' if symbol=='₹' else None,
               currency_label='印度卢比 INR' if symbol=='₹' else '$（币种代码未披露）',
               region_kind=reg[0], region_zh=reg[1], notes=notes.get(r['id'],[]))
    if row['has_attachments']:
        row['notes'].append('页面有附件；本轮未下载，摘要仅覆盖公开正文。')
    if r['id']=='661635': row['notes'].append('完整规格需保密协议，未获取。')
    if r['id']=='625444': row['notes'].append('来源说明更多细节将私下提供。')
    rows.append(row)

now = datetime.fromisoformat(raw['finished_at'].replace('Z','+00:00'))
counts = {str(days): sum(0 <= (now-datetime.fromisoformat(r['published_at'])).total_seconds() <= days*86400 for r in rows) for days in [3,30,90,365]}
report = {
 'question':'Truelancer 的公开项目能否支持一个本地、可搜索筛选的编程机会快照？',
 'verdict':f'已读取 100 个不同详情页，保留 {len(rows)} 条；可支撑页面实验，但旧记录很多，不证明稳定的新机会供给。',
 'max_listing_pages':12,'listing_pages_read':11,'listing_rows_seen':165,
 'max_unique_detail_pages':100,'unique_detail_pages_read':100,
 'retained_count':len(rows),'excluded_count':len(rejected),'blocked_count':0,
 'stop_reason':'达到预先设定的 100 个不同详情页上限；不追加请求补齐筛选后的数量。',
 'started_at':raw['started_at'],'finished_at':raw['finished_at'],
 'page_reads':111,'http_resource_requests':'未统计浏览器图片、脚本等资源请求；111 只表示顶层页面读取次数。',
 'status_counts':dict(Counter(r['source_status'] for r in rows)),
 'category_counts':dict(Counter(r['category'] for r in rows)),
 'age_counts_days':counts,'currency_counts':dict(Counter(r['currency_label'] for r in rows)),
 'region_counts':dict(Counter(r['region_kind'] for r in rows)),
 'limitations':['来自 programming 关键词公开列表，非全站、非随机样本。','Active 仅是来源显示状态，不证明雇主真实或现在仍可承接。','发布时间来自页面 time 节点，epoch 与带时区的 title 已逐条核对。','中文摘要由 Codex 根据公开正文概括，附件与外部链接未打开。','没有官方接口接入；不代表批量使用授权或持续采集稳定性已确认。','刷新页面只读取本地快照，不访问 Truelancer。'],
}
snapshot = {'prototype':True,'snapshot_at':raw['finished_at'],'candidates':rows,'excluded':rejected,'report':report}
assert len(rows) + len(rejected) == 100
assert len({r['id'] for r in rows}) == len(rows)
assert len({r['url'] for r in rows}) == len(rows)
(ROOT/'truelancer-snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
(ROOT/'data.js').write_text('/* PROTOTYPE: immutable one-off snapshot; no network collector. */\nwindow.TRUELANCER_SNAPSHOT = '+json.dumps(snapshot,ensure_ascii=False).replace('<','\\u003c')+';\n')
(ROOT/'validation.json').write_text(json.dumps({'unique_records':len(rows),'excluded':len(rejected),'budget_present':sum(bool(r['budget_raw']) for r in rows),'date_epoch_matches_title':len(rows),'chinese_summary_present':sum(bool(r['summary_zh']) for r in rows),'region_labels_present':sum(bool(r['region_zh']) for r in rows)},indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
