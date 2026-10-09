import {research,scenario,sensitivity,labels,routes,validateImport,hash,compareReports} from './engine.mjs';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const storeKey='chainscope-v1';
let persisted={pending:[],reviewed:[],snapshots:[]};
try{const x=JSON.parse(localStorage.getItem(storeKey));if(x&&Array.isArray(x.pending)&&Array.isArray(x.reviewed)&&Array.isArray(x.snapshots))persisted=x;}catch{}
let data,report,api=false,view='chain',node=null,market='all',level='all',event='lithium_down',reviewId=null,busy=false;
function persist(){try{localStorage.setItem(storeKey,JSON.stringify(persisted));}catch{toast('浏览器存储不可用或已满；请导出快照保存。');}}
let toastTimer;function toast(msg){$('#toast').textContent=msg;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,3500);}
function error(msg){$('#error').textContent=msg;$('#error').hidden=!msg;}
function download(name,value,type='application/json'){const blob=new Blob([typeof value==='string'?value:JSON.stringify(value,null,2)],{type});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
const byCompany=id=>data.companies.find(c=>c.id===id), byNode=id=>data.nodes.find(n=>n.id===id), byEvidence=id=>data.evidence.find(e=>e.id===id);
function badge(l){return `<span class="badge ${esc(l)}">${esc(l)} · ${esc(labels[l])}</span>`;}
function sourceLink(e){try{const u=new URL(e.url);if(u.protocol!=='https:')return '';}catch{return '';}return `<a href="${esc(e.url)}" target="_blank" rel="noopener noreferrer">打开来源原文 ↗</a>`;}
function empty(msg,sub=''){return `<div class="empty">${esc(msg)}${sub?`<small>${esc(sub)}</small>`:''}</div>`;}
function evidenceLinks(ids){return ids.map(id=>{const e=byEvidence(id);return e?`<button class="text-button" data-source="${esc(id)}">${esc(e.title)} ↗</button>`:'';}).join('');}
async function fetchJSON(url,options={}){const res=await fetch(url,options);const body=await res.json();if(!res.ok)throw Error(body.detail?.message||JSON.stringify(body.detail)||`请求失败 ${res.status}`);return body;}
function reviewedLocalData(base){const d=structuredClone(base);if(api)return d;for(const e of persisted.reviewed){if(!d.evidence.some(x=>x.id===e.id)){d.evidence.push(e);let r=d.relations.find(r=>r.company_id===e.company_id&&r.node_id===e.node_id&&r.route===e.route);if(r)r.evidence_ids.push(e.id);else d.relations.push({id:'r-'+e.id,company_id:e.company_id,node_id:e.node_id,route:e.route,evidence_ids:[e.id]});}}return d;}
let seed;
async function run({save=true}={}){
 if(busy)return;busy=true;$('#research').disabled=true;$('#loading').hidden=false;error('');
 try{
  data=reviewedLocalData(seed);
  const query=$('#industry').value.trim(),asOf=$('#asof').value,route=$('#route').value;
  report=api?await fetchJSON('/api/v1/research/industry',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({industry_name:query,as_of:asOf,route})}):await research(data,query,asOf,route);
  // Backend may contain server-reviewed imports unknown to the bundled JSON.
  if(api)for(const r of report.evidence_graph)for(const e of r.citation_source)if(!data.evidence.some(x=>x.id===e.id))data.evidence.push({...e,company_id:r.company_id,node_id:r.node_id,route:r.route});
  render();if(save)saveSnapshot(false);
 }catch(e){error(e.message+(report?' 以下仍为上一次成功核验的固态电池快照。':''));}
 finally{busy=false;$('#research').disabled=false;$('#loading').hidden=true;}
}
function render(){
 if(!report)return;
 const latest=report.evidence_graph.flatMap(r=>r.citation_source.map(e=>e.published_at)).sort().at(-1)||'无可用材料';
 $('#data-notice').textContent=`基线截止 ${data.meta.data_as_of}；本次纳入材料最新 ${latest}；来源复核 ${data.meta.reviewed_at}，证据截止 ${report.as_of}。证券标识沿用基线，不代表当前上市信息`;
 const rs=report.evidence_graph,cts=Object.fromEntries(['A','B','C','D','M'].map(l=>[l,rs.filter(r=>r.evidence_level===l).length]));
 $('#stats').innerHTML=[['覆盖公司',report.companies.length,'中国 / 美国 / 日本','◌'],['业务关系',rs.length,'按公司、环节与技术路径核验','↔'],['收入证据',cts.A,'仅计入同口径已实现收入','A'],['待确认收入',rs.length-cts.A,'研发、计划或数据缺失','?']].map(([label,n,sub,mark],i)=>`<div class="stat ${i===2?'accent':''}"><label>${label}</label><strong>${n}<b>${mark}</b></strong><small>${sub}</small></div>`).join('');
 $('#chain-map').innerHTML=report.hierarchy.map(n=>{const rels=rs.filter(r=>r.node_id===n.id),valid=rels.filter(r=>r.decision==='supported');return `<button class="chain-node ${node===n.id?'selected':''}" data-node="${n.id}" aria-pressed="${node===n.id}" title="${esc(n.description)}"><span class="stage">${esc(n.stage)} / ${String(n.order).padStart(2,'0')}</span><strong>${esc(n.name)}</strong><span class="node-count">${valid.length?valid.length+' 条已核验关系':rels.length?rels.length+' 个待核候选':'待补充同口径证据'}</span><span class="node-bar">${rels.length?rels.map(r=>`<span class="${esc(r.evidence_level)}"></span>`).join(''):'<span></span>'}</span></button>`;}).join('');
 $('#chain-map').insertAdjacentHTML('beforeend', `<div class="map-links">${report.edges.map(([a,b])=>`<span>${esc(byNode(a).name)} <b>→</b> ${esc(byNode(b).name)}</span>`).join('')}</div>`);
 renderCompanies();renderCompare();renderTransmission();renderEvidence();
}
function renderCompanies(){
 const list=report.evidence_graph.filter(r=>(!node||r.node_id===node)&&(market==='all'||byCompany(r.company_id)?.market===market)&&(level==='all'||r.evidence_level===level));
 $('#company-title').textContent=node?`${byNode(node).name} · 公司归属`:'公司与业务关系';
 $('#company-subtitle').textContent=`${list.filter(r=>r.decision==='supported').length} 条已核验关系 / ${list.filter(r=>r.decision!=='supported').length} 条待核候选 · 点击查看口径`;
 $('#clear-node').hidden=!node;
 $('#company-list').innerHTML=list.length?list.map(r=>{const c=byCompany(r.company_id);return `<article class="company-row" data-relation="${esc(r.id)}" tabindex="0" role="button" aria-label="查看${esc(c.name)}${esc(byNode(r.node_id).name)}证据"><div><div class="company-name">${esc(c.name)} <span class="market">${esc(c.market)}</span></div><span class="ticker">${esc(c.ticker)}</span></div><div class="relation-name">${esc(byNode(r.node_id).name)}<br><span class="route-label">${esc(routes[r.route])}</span></div><div class="row-claim">${badge(r.evidence_level)}${r.stale?'<span class="stale-label">历史材料 · 待跟进</span>':''}<div class="claim-short">${r.financial?`<strong>约 ${esc((r.financial.revenue_amount/10000).toLocaleString('zh-CN'))} 万${({USD:'美元',CNY:'元',JPY:'日元',HKD:'港元'})[r.financial.currency]} · ${esc(r.financial.period)}</strong><br>`:''}${esc(r.grade_reason)}</div></div><span class="row-action">查看证据 ↗</span></article>`;}).join(''):empty('当前条件下没有通过核验的业务关系',level==='D'?'不为展示传闻等级而编造公司传闻。':node==='lithium'?'一般锂盐业务不能直接作为固态专属业务的归属依据。':'可调整市场、技术路径或证据截止日期。');
}
function showRelation(id){
 const r=report.evidence_graph.find(r=>r.id===id);if(!r)return;
 const c=byCompany(r.company_id);
 $('#detail-body').innerHTML=`<h2 class="detail-title">${esc(c.name)}</h2><div class="detail-sub">${esc(c.ticker)} · ${esc(byNode(r.node_id).name)} · ${esc(routes[r.route])}</div>${badge(r.evidence_level)}<p>${esc(r.grade_reason)}</p>${r.financial?`<div class="financial-fact"><span>${esc(r.financial.period)} 年度 · 同口径已实现收入</span><strong>约 ${(r.financial.revenue_amount/10000).toLocaleString('zh-CN')} 万${({USD:'美元',CNY:'元',JPY:'日元',HKD:'港元'})[r.financial.currency]}</strong>${esc(r.financial.revenue_scope)}<br>收入占比：未披露 / 不计算</div>`:''}<div class="detail-warning">${r.route!=='all_solid'?'此关系为相邻技术，不能直接替代全固态业务证据。':'评级仅对本环节与技术路径有效，不能迁移到公司其他业务。'}${r.stale?' 材料距今超过一年，请核对后续进展。':''}</div>${r.citation_source.length?r.citation_source.map(e=>evidenceItem(e)).join(''):empty('证据缺失','缺失不等于该公司实际上没有业务或收入。')}`;
 $('#detail').showModal();
}
function evidenceItem(e){return `<div class="evidence-item"><h4>${esc(e.title)}</h4><p>${esc(e.summary)}</p>${sourceLink(e)}<small>发布日期 ${esc(e.published_at)} · 定位：${esc(e.locator)}</small><small>证据 ID ${esc(e.id)} · 摘要 SHA-256 ${(esc(e.summary_hash)||'').slice(0,24)}…</small></div>`;}
function showSource(id){const e=byEvidence(id);if(!e)return;$('#detail-body').innerHTML=`<h2 class="detail-title">来源与结论</h2>${evidenceItem(e)}<div class="detail-warning">来源支持的是其披露时点的事实或计划，不自动证明最新进展。摘要哈希仅校验本地摘要。</div>`;$('#detail').showModal();}
function renderCompare(){
 $('#comparisons').innerHTML=report.comparisons.length?report.comparisons.map(c=>`<article class="compare-card"><div class="compare-top"><div><h3>${esc(c.title)}</h3><p>${esc(c.basis)}</p></div><span class="pill">${esc(c.verdict)}</span></div><div class="compare-grid"><div class="compare-column"><h4>为何可比</h4><ul>${c.comparable.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div><div class="compare-column limit"><h4>哪些不可比</h4><ul>${c.not_comparable.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div></div><div class="citations"><span>依据 · 分析判断</span>${evidenceLinks(c.evidence_ids)}</div></article>`).join(''):empty('当前截止日期或技术筛选下，可比分析的证据基础不完整','调整条件后重新核验；不会引用未来材料补齐对照。');
}
let transmissionRevision=0;
async function renderTransmission(){
 const revision=++transmissionRevision;
 $('#event-tabs').innerHTML=data.scenarios.map(s=>`<button data-event="${s.id}" class="${event===s.id?'active':''}">${esc(s.event)}</button>`).join('');
 let s;
 try{s=api?await fetchJSON('/api/v1/research/transmission?'+new URLSearchParams({industry:'固态电池',event,as_of:report.as_of,route:report.route})):scenario(data,report,event);}catch(e){if(revision===transmissionRevision)$('#transmission').innerHTML=empty('传导分析失败',e.message);return;}
 if(revision!==transmissionRevision)return;
 $('#transmission').innerHTML=`<div class="event-intro"><div class="event-icon">⌁</div><div><h3>${esc(s.event)}</h3><p>${esc(s.summary)}</p></div></div>${s.paths.length?s.paths.map((p,i)=>`<article class="path-card"><div class="path-node"><small>传导分支 ${String(i+1).padStart(2,'0')} · ${esc(byNode(p.node_id).stage)}</small><h3>${esc(byNode(p.node_id).name)}</h3><p>${p.company_ids.map(id=>esc(byCompany(id).name)).join(' / ')}</p><span class="pill">${esc(p.direction)}</span></div><div class="path-business"><h4>业务变化 → 待验证指标</h4><p>${esc(p.business_effect)}</p><p class="conditions">成立条件：${p.assumptions.map(esc).join('；')}</p><p>反向机制：${esc(p.counter)}</p><p><small>${esc(p.evidence_limit)}</small></p><div>${evidenceLinks(p.evidence_ids)}</div></div><div class="path-metrics"><label>观察财务指标</label>${p.metrics.map(m=>`<span class="metric-tag">${esc(m)}</span>`).join('')}<small>没有公司级量化参数<br>不生成盈利增幅或目标价</small></div></article>`).join(''):empty('该情景所需证据在当前截止日期下不完整')}${s.kind==='cost'?`<section class="scenario-box"><h3>成本敏感度 · 自定义假设</h3><p>固定销量与基期收入的毛利额贡献示意。全部参数为用户假设，不是任何公司的已披露参数。</p><div class="slider-grid"><div class="slider"><label for="price-slider">原料价格变化 <output id="price-output">−20%</output></label><input type="range" id="price-slider" min="-50" max="50" value="-20"></div><div class="slider"><label for="share-slider">原料成本 / 基期收入 <output id="share-output">30%</output></label><input type="range" id="share-slider" min="0" max="100" value="30"></div><div class="slider"><label for="pass-slider">降本转移给客户比例 <output id="pass-output">70%</output></label><input type="range" id="pass-slider" min="0" max="100" value="70"></div><div class="calc-result"><strong id="calc-output">+1.80 pp</strong><small>毛利额 / 基期收入的增量<br>不是公司毛利率预测</small></div></div><div class="formula">贡献百分点 = −价格变化 × 原料成本占比 × (1 − 转移比例) × 100<br>不含销量、售价分母变化、库存时滞、税费及良率影响。</div></section>`:''}`;
}
function renderEvidence(){
 const activeIds=new Set(report.evidence_graph.flatMap(r=>r.citation_source.map(e=>e.id)));
 const sources=data.evidence.filter(e=>activeIds.has(e.id));
 $('#evidence-metrics').innerHTML=`<div><strong>${sources.length}</strong>通过当前时间与口径校验</div><div><strong>${new Set(sources.map(e=>e.url)).size}</strong>独立原始材料</div><div><strong>${persisted.pending.length}</strong>条新证据待人工复核</div>`;
 $('#evidence-table').innerHTML=sources.length?`<table><thead><tr><th>来源 / 业务关系</th><th>发布日期</th><th>环节 / 路径</th><th>定位与校验</th><th>操作</th></tr></thead><tbody>${sources.map(e=>`<tr><td>${esc(e.title)}<small>${esc(byCompany(e.company_id)?.name)}</small></td><td>${esc(e.published_at)}<small>历史证据</small></td><td>${esc(byNode(e.node_id)?.name)}<small>${esc(routes[e.route])}</small></td><td>${esc(e.locator)}<small>摘要 ${esc(e.summary_hash?.slice(0,10))}…</small></td><td><button class="text-button" data-source="${esc(e.id)}">查看原文 ↗</button></td></tr>`).join('')}</tbody></table>`:empty('没有通过当前截止日期核验的来源');
 $('#pending-count').textContent=`${persisted.pending.length} 条待审`;
 $('#pending-list').innerHTML=persisted.pending.length?persisted.pending.map(e=>`<div class="pending-row"><div>${esc(e.title)}<small>${esc(byCompany(e.company_id)?.name)} · ${esc(e.published_at)} · 导入不会自动升级证据等级</small></div><button class="text-button" data-review="${esc(e.id)}">核对并复核</button></div>`).join(''):empty('暂无待审证据','可导入新的公告、财报或官方材料；仅修改抓取日期不会提升证据新鲜度。');
 renderSnapshots();
 $('#workflow-trace').innerHTML=`<div class="trace">${report.trace.map(n=>`<span>✓ ${esc(n.node)}</span>`).join('')}</div>`;
}
function saveSnapshot(showToast=true){
 if(!report)return;
 if(!persisted.snapshots.some(s=>s.id===report.snapshot_id)){
  persisted.snapshots.unshift({id:report.snapshot_id,created_at:new Date().toISOString(),report:structuredClone(report)});persisted.snapshots=persisted.snapshots.slice(0,20);persist();
 }
 renderSnapshots();if(showToast)toast(api?'后端与浏览器快照已保存':'快照已保存到当前浏览器');
}
function renderSnapshots(){
 $('#snapshots').innerHTML=persisted.snapshots.length?persisted.snapshots.map((s,i)=>`<div class="snapshot-row"><div>固态电池 · 证据截止 ${esc(s.report.as_of)}<small>${new Date(s.created_at).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'})} · ${esc(s.id.slice(0,12))} · ${esc(s.report.ai_mode)}</small></div><div class="snapshot-actions"><button class="text-button" data-snapshot="${esc(s.id)}">导出</button>${i<persisted.snapshots.length-1?`<button class="text-button" data-diff="${esc(s.id)}">对照上一版本</button>`:''}</div></div>`).join(''):empty('尚无研究快照');
}
function showDiff(id){
 const i=persisted.snapshots.findIndex(s=>s.id===id),s=persisted.snapshots[i],prev=persisted.snapshots[i+1];if(!prev)return;
 const diff=compareReports(prev.report,s.report),fieldNames={revenue_amount:'收入金额',currency:'币种',period:'财务期间',revenue_scope:'业务范围',revenue_share:'收入占比'};
 const sourceChanges=(es,label)=>es.map(e=>`<li><strong>${label}</strong> ${esc(e.title)} · ${esc(e.published_at)}${sourceLink(e)}</li>`).join('');
 const changes=diff.changes.map(c=>`<section class="diff-item"><h3>${esc(byCompany(c.company_id)?.name)} · ${esc(byNode(c.node_id)?.name)}</h3><p>${c.grade_changed?`等级 ${esc(c.previous_level||'未纳入')} → ${esc(c.level)}`:`等级保持 ${esc(c.level)}`}${c.decision_changed?' · 核验状态改变':''}</p><ul>${sourceChanges(c.added_evidence,'新增来源')}${sourceChanges(c.removed_evidence,'移除来源')}${sourceChanges(c.updated_evidence,'材料内容更新')}${c.financial_changes.map(f=>`<li>${fieldNames[f.field]}：${esc(f.before??'未披露')} → ${esc(f.after??'未披露')}</li>`).join('')}</ul></section>`).join('');
 const removed=diff.excluded.map(r=>`<p>${esc(byCompany(r.company_id)?.name)} · ${esc(byNode(r.node_id)?.name)}：本次条件未纳入</p>`).join('');
 $('#detail-body').innerHTML=`<h2 class="detail-title">快照差异</h2><div class="detail-sub">${esc(prev.report.as_of)} → ${esc(s.report.as_of)}</div><div class="detail-warning">${diff.filters_changed?'本次筛选或证据截止日期改变。':'研究条件一致。'}材料变化不自动代表公司业务发生变化，新增来源仍需核对原文。</div>${changes||removed?changes+removed:empty('业务关系、来源和财务字段没有变化')}`;$('#detail').showModal();
}
function setView(v){view=v;$$('.view').forEach(el=>el.hidden=el.id!==v+'-view');$$('.nav').forEach(b=>b.classList.toggle('active',b.dataset.view===v));const names={chain:'产业图谱',compare:'跨市场对照',transmission:'传导路径',evidence:'证据与更新'};$('#breadcrumb').textContent=names[v];$('#page-title').textContent={chain:'把产业关系，落到证据上。',compare:'比较公司，先比较业务。',transmission:'看清变化，沿链路追踪。',evidence:'每次更新，都有迹可循。'}[v];window.scrollTo(0,0);$('#page-subtitle').textContent={chain:'从产业环节到公司业务，逐条核验关联的真实程度。',compare:'解释为何可比，以及技术、客户和商业模式的差异。',transmission:'从外部情景到业务变化，保留成立条件与反向机制。',evidence:'保留来源、材料时点和审阅记录，让结论可以被复核。'}[v];}
const template={company_id:'qs',node_id:'cell',route:'solid_separator',title:'请填写官方材料标题',url:'https://www.quantumscape.com/powerco-and-quantumscape-announce-landmark-agreement-to-industrialize-solid-state-batteries/',published_at:'2024-07-11',kind:'research',summary:'请阅读原文后填写客观摘要，并写明哪些结论没有足够证据。',locator:'Official release · Agreement',source_type:'official_material'};
document.addEventListener('click',async ev=>{
 const b=ev.target.closest('button,[data-relation]');if(!b)return;
 if(b.dataset.view)setView(b.dataset.view);
 if(b.dataset.node){node=node===b.dataset.node?null:b.dataset.node;render();}
 if(b.dataset.market){market=b.dataset.market;$$('[data-market]').forEach(x=>x.classList.toggle('selected',x.dataset.market===market));renderCompanies();}
 if(b.dataset.relation)showRelation(b.dataset.relation);
 if(b.dataset.source)showSource(b.dataset.source);
 if(b.dataset.close)$('#'+b.dataset.close).close();
 if(b.dataset.event){event=b.dataset.event;renderTransmission();}
 if(b.dataset.snapshot){const s=persisted.snapshots.find(s=>s.id===b.dataset.snapshot);download(`chainscope-${s.id.slice(0,12)}.json`,s.report);}
 if(b.dataset.diff)showDiff(b.dataset.diff);
 if(b.dataset.review){reviewId=b.dataset.review;const e=persisted.pending.find(e=>e.id===reviewId);$('#review-body').innerHTML=evidenceItem(e);$('#review-check').checked=false;$('#review-confirm').disabled=true;$('#review-dialog').showModal();}
});
$('#research-form').addEventListener('submit',e=>{e.preventDefault();run();});
$('#route').addEventListener('change',()=>{node=null;run();});
$('#level').addEventListener('change',()=>{level=$('#level').value;renderCompanies();});
$('#clear-node').addEventListener('click',()=>{node=null;render();});
$('#export').addEventListener('click',()=>report&&download(`chainscope-solid-state-${report.as_of}.json`,report));
$('#save-snapshot').addEventListener('click',()=>saveSnapshot());
$('#template-download').addEventListener('click',()=>download('evidence-import-template.json',template));
$("#evidence-input").addEventListener("submit",e=>e.preventDefault());
let importMode='form';
function setImportMode(mode){importMode=mode;$('#evidence-input').hidden=mode!=='form';$('#json-import').hidden=mode!=='json';$$('[data-import-mode]').forEach(b=>{b.classList.toggle('selected',b.dataset.importMode===mode);b.setAttribute('aria-pressed',b.dataset.importMode===mode);});}
function renderImportForm(){
 $('#e-company').innerHTML=data.companies.map(c=>`<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('');
 $('#e-node').innerHTML=data.nodes.map(n=>`<option value="${esc(n.id)}">${esc(n.name)}</option>`).join('');
 $('#e-route').innerHTML=Object.entries(routes).map(([id,label])=>`<option value="${id}">${esc(label)}</option>`).join('');
}
function syncRevenueFields(){const active=$('#e-kind').value==='revenue';$('#revenue-fields').hidden=!active;$('#revenue-fields').disabled=!active;if(active)$('#e-source-type').value='annual_report';}
function formEvidence(){
 const v=Object.fromEntries(new FormData($('#evidence-input')));if(v.kind==='revenue'){if(v.revenue_amount!=='')v.revenue_amount=Number(v.revenue_amount);else delete v.revenue_amount;for(const k of ['period','revenue_scope'])if(!v[k].trim())delete v[k];}return v;
}
$$('[data-import-mode]').forEach(b=>b.addEventListener('click',()=>setImportMode(b.dataset.importMode)));
$('#e-kind').addEventListener('change',syncRevenueFields);
$('#import-open').addEventListener('click',()=>{renderImportForm();syncRevenueFields();$('#admin-field').hidden=!api;$('#import-error').textContent='';$('#import-dialog').showModal();});
$('#update-sample').addEventListener('click',async()=>{
 try{const sample=await fetchJSON('./update-sample.json');renderImportForm();setImportMode('form');
  for(const [k,v] of Object.entries(sample)){const field=$('#evidence-input').elements.namedItem(k);if(field)field.value=v;}
  syncRevenueFields();$('#admin-field').hidden=!api;$('#import-error').textContent='此更新样本来自 2026-02-25 发布的年报。复核后，还需将证据截止设至该日或更晚，才会参与评级。';$('#import-dialog').showModal();
 }catch(e){error('更新样本读取失败：'+e.message);}
});
$('#import-file').addEventListener('change',async e=>{const f=e.target.files[0];if(!f)return;if(f.size>100000){$('#import-error').textContent='文件请小于 100 KB';return;}$('#import-json').value=await f.text();});
$('#import-submit').addEventListener('click',async()=>{
 try{if(importMode==='form'&&!$('#evidence-input').reportValidity())return;const raw=importMode==='form'?formEvidence():JSON.parse($('#import-json').value),entry=await validateImport(raw,data);if(persisted.pending.some(e=>e.id===entry.id)||persisted.reviewed.some(e=>e.id===entry.id))throw Error('这条证据已导入');
  if(api){const result=await fetchJSON('/api/v1/evidence',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+$('#admin-token').value},body:JSON.stringify(raw)});entry.id=result.id;}
  persisted.pending.push(entry);persist();$('#import-dialog').close();renderEvidence();toast('已加入待审区；评级保持原状');
 }catch(e){$('#import-error').textContent=e.message;}
});
$('#review-check').addEventListener('change',()=>$('#review-confirm').disabled=!$('#review-check').checked);
$('#review-confirm').addEventListener('click',async()=>{
 if(!$('#review-check').checked)return;
 try{let e=persisted.pending.find(e=>e.id===reviewId);if(!e)return;
  if(api)await fetchJSON('/api/v1/evidence/'+encodeURIComponent(e.id)+'/review',{method:'POST',headers:{Authorization:'Bearer '+$('#admin-token').value}});
  else persisted.reviewed.push({...e,review_status:'reviewed',reviewed_at:new Date().toISOString().slice(0,10)});
  persisted.pending=persisted.pending.filter(x=>x.id!==reviewId);persist();$('#review-dialog').close();await run();toast('复核记录已保存，已按当前截止日期重新评级');
 }catch(e){error(e.message);$('#review-dialog').close();}
});
document.addEventListener('input',e=>{if(!['price-slider','share-slider','pass-slider'].includes(e.target.id))return;const price=+$('#price-slider').value,share=+$('#share-slider').value,pass=+$('#pass-slider').value;$('#price-output').textContent=price+'%';$('#share-output').textContent=share+'%';$('#pass-output').textContent=pass+'%';const n=sensitivity(price/100,share/100,pass/100);$('#calc-output').textContent=(n>0?'+':'')+n.toFixed(2)+' pp';});
document.addEventListener('keydown',e=>{const r=e.target.closest('[data-relation]');if(r&&(e.key==='Enter'||e.key===' ')){e.preventDefault();showRelation(r.dataset.relation);}});
try{
 seed=await fetchJSON('./research.json');data=reviewedLocalData(seed);
 try{const health=await fetchJSON('/api/v1/health',{signal:AbortSignal.timeout(1800)});api=health.backend==='FastAPI + LangGraph';}catch{}
 $('#mode').textContent=api?'FastAPI / LangGraph 已连接':'独立演示 · 浏览器规则引擎';
 await run();
}catch(e){error('数据加载失败：'+e.message);$('#mode').textContent='加载失败';}
