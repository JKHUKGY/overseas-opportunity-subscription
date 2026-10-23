'use strict';
// PROTOTYPE: local immutable data; searches and filters never contact the source.
const $ = id => document.getElementById(id);
const data = window.TRUELANCER_SNAPSHOT;
const pageSize = 12;
let filtered = [], selected = null, page = 1;
const filterIds = ['category','age','region','pricing','currency','status'];
function el(tag, cls, text) { const n = document.createElement(tag); if(cls)n.className=cls; if(text!==undefined)n.textContent=text; return n; }
function fmtDate(s, full=false) { return new Intl.DateTimeFormat('zh-CN', full ? {year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false} : {year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(s)); }
function ageDays(r) {return (Date.parse(data.snapshot_at)-Date.parse(r.published_at))/86400000;}
function pricing(r) {return r.pricing==='hourly'?'按小时':'固定价';}
function regionFlag(r){return ['restricted','preferred','onsite'].includes(r.region_kind);}
function applyFilters(reset=true) {
  if(reset)page=1;
  const q=$('search').value.trim().toLowerCase(), age=$('age').value;
  filtered=data.candidates.filter(r=>{
    if(q && ![r.title,r.summary_zh,r.id,r.region_zh,...r.skills].join(' ').toLowerCase().includes(q))return false;
    if($('category').value && r.category!==$('category').value)return false;
    if($('region').value && r.region_kind!==$('region').value)return false;
    if($('pricing').value && r.pricing!==$('pricing').value)return false;
    if($('currency').value && r.currency_symbol!==$('currency').value)return false;
    if($('status').value && r.source_status!==$('status').value)return false;
    if(age && (age==='older' ? ageDays(r)<=365 : ageDays(r)<0 || ageDays(r)>Number(age)))return false;
    return true;
  }).sort((a,b)=>($('sort').value==='oldest'?1:-1)*(Date.parse(a.published_at)-Date.parse(b.published_at)));
  page=Math.max(1,Math.min(page,Math.ceil(filtered.length/pageSize)));
  const visible=filtered.slice((page-1)*pageSize,page*pageSize);
  if(!visible.some(r=>r.id===selected))selected=visible[0]?.id||null;
  $('result-count').textContent=filtered.length;
  renderList();renderDetail();
}
function renderList(){
  const list=$('results');list.replaceChildren();
  if(!filtered.length)list.append(el('div','empty','没有符合条件的项目。试试其他关键词，或重置筛选。'));
  for(const r of filtered.slice((page-1)*pageSize,page*pageSize)){
    const b=el('button','candidate'+(selected===r.id?' selected':''));b.type='button';b.dataset.id=r.id;b.setAttribute('aria-pressed',String(selected===r.id));
    const top=el('div','row-top'), budget=el('div','row-budget',r.budget_raw);budget.append(el('small','',pricing(r)));top.append(el('h3','row-title',r.title),budget);
    const bottom=el('div','row-bottom');bottom.append(el('span','pill',r.category));
    if(regionFlag(r))bottom.append(el('span','pill warning',r.region_kind==='preferred'?'地区优先':'地区 / 现场要求'));
    if(r.source_status!=='Active')bottom.append(el('span','pill warning','冻结状态'));
    bottom.append(el('span','row-date',fmtDate(r.published_at)));
    b.append(top,el('p','row-desc',r.summary_zh),bottom);
    b.addEventListener('click',()=>{selected=r.id;renderList();renderDetail();if(matchMedia('(max-width:650px)').matches)$('detail').scrollIntoView({behavior:'smooth',block:'start'});});list.append(b);
  }
  $('page-number').textContent=`${page} / ${Math.max(1,Math.ceil(filtered.length/pageSize))}`;
  $('page-caption').textContent=filtered.length?`第 ${(page-1)*pageSize+1}–${Math.min(page*pageSize,filtered.length)} 条 · 共 ${filtered.length} 条`:'共 0 条';
  $('prev').disabled=page<=1;$('next').disabled=page*pageSize>=filtered.length;
}
function renderDetail(){
  const pane=$('detail');pane.replaceChildren();const r=data.candidates.find(r=>r.id===selected);
  if(!r){pane.append(el('div','empty','调整筛选条件后，可在这里查看项目。'));return;}
  const kicker=el('div','detail-kicker');kicker.append(el('span','','PROJECT / '+r.id),el('span','unverified',r.source_status));
  const budget=el('div','detail-budget',r.budget_raw);budget.append(el('small','',pricing(r)));
  const meta=el('dl','detail-meta');
  const facts=[['原始发布时间',fmtDate(r.published_at,true)],['原始币种',r.currency_label],['地区要求',r.region_zh],['列表预算原值',r.list_budget_raw||'未提供'],['平台显示状态',r.source_status+'；可承接性未确认'],['读取时间',fmtDate(r.observed_at,true)]];
  if(r.estimated_hours)facts.push(['页面预计工时',r.estimated_hours+' 小时（非承诺工时）']);
  for(const [name,value]of facts){const item=el('div');item.append(el('dt','',name),el('dd','',value));meta.append(item);}
  const skills=el('div','skill-tags');for(const s of r.skills)skills.append(el('span','',s));
  const excerpt=el('details','source-excerpt');excerpt.append(el('summary','','展开公开原文片段与时间证据'),el('p','',r.description_excerpt+' …'),el('p','',`页面时间原值：${r.published.title}；datetime=${r.published.datetime}；相对时间：${r.published.relative}。`));
  const notice=el('div','detail-notice'),ul=el('ul');
  const notes=[...r.notes];if(ageDays(r)>90)notes.push('发布已超过 90 天；本页展示历史快照中的平台状态。');notes.push('中文摘要依据公开正文；完整需求、预算口径和能否申请请以原帖核实。');
  for(const t of notes)ul.append(el('li','',t));notice.append(ul);
  const actions=el('div','detail-actions'),link=el('a','button primary','查看 Truelancer 原项目 ↗');
  const url=new URL(r.url);if(url.protocol==='https:'&&url.hostname==='www.truelancer.com'){link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';actions.append(link);}
  const copy=el('button','button secondary','复制链接');copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(r.url);copy.textContent='已复制';}catch{copy.textContent='请从原帖链接复制';}});actions.append(copy);
  pane.append(kicker,el('h2','',r.title),budget,el('p','budget-note','保留详情页原值；列表与详情可能使用不同币种，本页不做汇率换算。'),meta,el('h3','description-title','中文需求摘要'),el('div','description',r.summary_zh),skills,excerpt,notice,actions,el('div','detail-id',`Truelancer · ${r.id} · 时间按浏览器本地时区显示`));
}
function showEvidence(){
  const body=$('evidence-body');body.replaceChildren();const r=data.report;
  body.append(el('div','evidence-summary',r.verdict),el('p','',`访问了 ${r.listing_pages_read} 个列表页（${r.listing_rows_seen} 个卡片）和 ${r.unique_detail_pages_read} 个不同详情页。未遇到登录或验证码。${r.stop_reason}`),el('p','',`共 ${r.page_reads} 次顶层页面读取；浏览器资源请求未统计。观察时段：${fmtDate(r.started_at,true)} — ${fmtDate(r.finished_at,true)}。`));
  for(const t of r.limitations)body.append(el('p','',t));
  body.append(el('h3','','未纳入的 12 条记录'));
  const table=el('table','evidence-table'),head=el('tr');for(const t of ['项目 ID','未纳入原因'])head.append(el('th','',t));table.append(head);
  for(const x of data.excluded){const tr=el('tr'),cell=el('td'),a=el('a','',x.id);a.href=x.url;a.target='_blank';a.rel='noopener noreferrer';cell.append(a);tr.append(cell,el('td','',x.reason));table.append(tr);}body.append(table);$('evidence').showModal();
}
for(const category of Object.keys(data.report.category_counts).sort())$('category').append(new Option(category,category));
$('total-count').textContent=data.candidates.length;$('nav-count').textContent=data.candidates.length;
$('recent-count').textContent=data.report.age_counts_days['30'];$('region-count').textContent=data.candidates.filter(regionFlag).length;
$('checked-count').textContent=data.report.unique_detail_pages_read;$('collected-time').textContent=fmtDate(data.snapshot_at,true);
$('progress-caption').textContent=`已核查 100 个详情 · 保留 ${data.candidates.length} 条`;$('progress-bar').style.width=data.candidates.length+'%';
$('snapshot-note').textContent=`这是一份 ${fmtDate(data.snapshot_at)} 的本地快照：88 条中只有 5 条在近 30 天发布，31 条超过一年。平台显示 Active 也可能是旧项目，请结合时间与原帖判断。`;
$('search').addEventListener('input',()=>applyFilters());for(const id of [...filterIds,'sort'])$(id).addEventListener('change',()=>applyFilters());
$('reset').addEventListener('click',()=>{$('search').value='';for(const id of filterIds)$(id).value='';$('sort').value='newest';applyFilters();});
for(const [id,step]of [['prev',-1],['next',1]])$(id).addEventListener('click',()=>{page+=step;selected=filtered[(page-1)*pageSize]?.id||null;renderList();renderDetail();$('results').scrollTop=0;});
$('show-evidence').addEventListener('click',showEvidence);$('close-evidence').addEventListener('click',()=>$('evidence').close());
$('refresh').addEventListener('click',()=>location.reload());document.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('search').focus();}});
applyFilters();
