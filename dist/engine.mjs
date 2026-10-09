// Offline reference engine. Python/LangGraph is authoritative when the API is connected.
export const labels={A:'已实现收入',B:'研发 / 产线',C:'计划 / 表态',D:'市场传闻',M:'数据缺失'};
export const routes={all_solid:'全固态',semi_solid:'半固态',condensed:'凝聚态（相邻技术）',solid_separator:'固态隔膜（含液态正极）'};
export const officialDomains=new Set(['sec.gov','www.sec.gov','global.toyota','www.catl.com','www.ganfenglithium.com','www.quantumscape.com','www.solidpowerbattery.com','ir.solidpowerbattery.com']);
export async function hash(text){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)))).map(b=>b.toString(16).padStart(2,'0')).join('');}
const dateOnly=v=>/^\d{4}-\d{2}-\d{2}$/.test(v)&&!isNaN(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v;
function validPeriod(e,asOf){if(!/^\d{4}(Q[1-4])?$/.test(e.period||''))return false;const year=+e.period.slice(0,4),month=e.period.includes('Q')?+e.period.slice(-1)*3:12;const end=new Date(Date.UTC(year,month,0)).toISOString().slice(0,10);return end<=e.published_at&&end<=asOf;}
export async function grade(relation,evidence,asOf){
 let usable=[];
 for(const e of evidence){
  let validUrl=false;try{const u=new URL(e.url);validUrl=u.protocol==='https:'&&officialDomains.has(u.hostname)&&!u.username&&!u.password;}catch{}
  if(relation.evidence_ids.includes(e.id)&&e.company_id===relation.company_id&&e.node_id===relation.node_id&&e.route===relation.route&&e.review_status==='reviewed'&&dateOnly(e.published_at)&&e.published_at<=asOf&&e.locator&&validUrl&&e.summary_hash===await hash(e.summary))usable.push(e);
 }
 let level='M',financial=null,decision='unsupported',reason='没有通过核验的同口径证据';
 if(usable.some(e=>e.conflicted)){decision='conflicted';reason='存在互相矛盾的证据，需人工复核';}
 else for(const [l,kind] of [['A','revenue'],['B','research'],['C','statement'],['D','rumor']]){
  const e=usable.find(e=>e.kind===kind&&(l!=='A'||(e.source_type==='annual_report'&&Number.isFinite(e.revenue_amount)&&e.revenue_amount>0&&e.currency&&validPeriod(e,asOf)&&e.revenue_scope)));
  if(e){level=l;decision=l==='D'?'unsupported':'supported';reason={A:'同口径财报收入；不代表量产电芯销售',B:'有研发、送样或产线进展；独立收入未确认',C:'仅支持未来业务计划或表态',D:'市场传闻不能证明真实业务'}[l];if(l==='A')financial={revenue_amount:e.revenue_amount,currency:e.currency,period:e.period,revenue_scope:e.revenue_scope,amount_is_rounded:e.amount_is_rounded,revenue_share:null};break;}
 }
 return {...relation,evidence_level:level,financial,decision,grade_reason:reason,citation_source:usable,stale:usable.length>0&&usable.every(e=>(Date.now()-Date.parse(e.published_at))/86400000>365),missing_reason:usable.length?null:'无可用证据；不等于事实上的零收入'};
}
export async function research(data,query='固态电池',asOf='2025-03-01',route='all'){
 if(/买入|卖出|目标价|推荐股票|必涨|稳赚|buy\s+or\s+sell|price\s+target/i.test(query))throw Error('不提供买卖建议、目标价或确定性收益预测。');
 if(!data.meta.aliases.some(a=>a.toLowerCase()===query.trim().toLowerCase()))throw Error('当前已核验数据仅覆盖固态电池，不能生成其他产业的真实研究结果。');
 if(!dateOnly(asOf))throw Error('请输入有效的证据截止日期。');
 const relations=await Promise.all(data.relations.filter(r=>route==='all'||route===r.route).map(r=>grade(r,data.evidence,asOf)));
 const supported=new Set(relations.filter(r=>r.decision==='supported').flatMap(r=>r.citation_source.map(e=>e.id)));
 const companies=data.companies.filter(c=>relations.some(r=>r.company_id===c.id)).map(c=>({...c,relations:relations.filter(r=>r.company_id===c.id)}));
 const comparisons=data.comparisons.filter(c=>companies.some(x=>x.id===c.left)&&companies.some(x=>x.id===c.right)&&c.evidence_ids.every(id=>supported.has(id))).map(c=>({...c,claim_type:'analyst_inference'}));
 const report={meta:data.meta,as_of:asOf,route,hierarchy:data.nodes,edges:data.edges,companies,evidence_graph:relations,comparisons,ai_mode:'browser_reference',claims:data.evidence.filter(e=>supported.has(e.id)).map(e=>({text:e.summary,evidence_ids:[e.id],decision:'supported'})),trace:['IntentParser','IndustryStructurer','CompanyLocatorEvidenceGrader','CrossMarketComparator','TransmissionTracer','ReportGate'].map(node=>({node,status:'ok'})),boundary:'研究辅助，不提供买卖建议或目标价。'};
 report.snapshot_id=await hash(JSON.stringify(report));return report;
}
export function sensitivity(price,share,pass){if(![price,share,pass].every(Number.isFinite)||price< -1||price>1||share<0||share>1||pass<0||pass>1)throw Error('情景参数超出范围');return Math.round(-price*share*(1-pass)*100*10000)/10000;}
export function scenario(data,report,event){
 const item=data.scenarios.find(s=>s.id===event||s.event===event);if(!item)throw Error('未支持的情景');
 const supported=new Set(report.evidence_graph.filter(r=>r.decision==='supported').flatMap(r=>r.citation_source.map(e=>e.id)));
 const entities=new Map(data.evidence.map(e=>[e.id,e.company_id]));
 const paths=item.paths.flatMap(p=>{
  const company_ids=p.company_ids.filter(cid=>{const ids=p.evidence_ids.filter(id=>entities.get(id)===cid);return ids.length&&ids.every(id=>supported.has(id));});
  return company_ids.length?[{...p,company_ids,evidence_ids:p.evidence_ids.filter(id=>company_ids.includes(entities.get(id))),claim_type:'scenario_inference',numeric_impact:null}]:[];
 });
 return {...item,paths,event_verified:false};
}
export function compareReports(before,after){
 const old=new Map(before.evidence_graph.map(r=>[r.id,r]));
 const changes=after.evidence_graph.flatMap(r=>{
  const prev=old.get(r.id),a=new Map((prev?.citation_source||[]).map(e=>[e.id,e])),b=new Map(r.citation_source.map(e=>[e.id,e]));
  const added=[...b.values()].filter(e=>!a.has(e.id)),removed=[...a.values()].filter(e=>!b.has(e.id));
  const updated=[...b.values()].filter(e=>a.has(e.id)&&JSON.stringify(e)!==JSON.stringify(a.get(e.id)));
  const financial_fields=['revenue_amount','currency','period','revenue_scope','revenue_share'];
  const financial_changes=financial_fields.filter(k=>(prev?.financial?.[k]??null)!==(r.financial?.[k]??null)).map(field=>({field,before:prev?.financial?.[field]??null,after:r.financial?.[field]??null}));
  const grade_changed=prev?.evidence_level!==r.evidence_level,decision_changed=prev?.decision!==r.decision;
  if(prev&&!grade_changed&&!decision_changed&&!added.length&&!removed.length&&!updated.length&&!financial_changes.length)return [];
  return [{id:r.id,company_id:r.company_id,node_id:r.node_id,route:r.route,previous_level:prev?.evidence_level??null,level:r.evidence_level,grade_changed,decision_changed,added_evidence:added,removed_evidence:removed,updated_evidence:updated,financial_changes}];
 });
 const excluded=before.evidence_graph.filter(r=>!after.evidence_graph.some(x=>x.id===r.id));
 return {filters_changed:before.as_of!==after.as_of||before.route!==after.route,changes,excluded};
}
export async function validateImport(v,data){
 const allowed=['company_id','node_id','route','title','url','published_at','kind','summary','locator','source_type','revenue_amount','currency','period','revenue_scope'];
 if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).some(k=>!allowed.includes(k)))throw Error('证据 JSON 包含未知字段，不能自行声明 reviewed / verified。');
 if(!data.companies.some(c=>c.id===v.company_id)||!data.nodes.some(n=>n.id===v.node_id)||!Object.keys(routes).includes(v.route))throw Error('公司、环节或技术路径无效。');
 for(const [k,min,max] of [['title',2,200],['summary',10,3000],['locator',2,300],['url',1,2000]])if(typeof v[k]!=='string'||v[k].length<min||v[k].length>max)throw Error(k+' 字段不完整或超长');
 const u=new URL(v.url);if(u.protocol!=='https:'||!officialDomains.has(u.hostname)||u.username||u.password)throw Error('仅接受已登记官方来源的 HTTPS 链接。');
 if(!dateOnly(v.published_at)||v.published_at>new Date().toISOString().slice(0,10))throw Error('发布日期无效或晚于今天。');
 if(!['revenue','research','statement','rumor'].includes(v.kind)||!['annual_report','official_material','news'].includes(v.source_type))throw Error('证据类型无效');
 if(v.revenue_amount!=null&&(!Number.isFinite(v.revenue_amount)||v.revenue_amount<=0))throw Error('收入金额须大于 0；未知请留空。');
 if(v.currency!=null&&!['CNY','USD','JPY','HKD'].includes(v.currency))throw Error('币种无效');
 if(v.period!=null&&!/^\d{4}(Q[1-4])?$/.test(v.period))throw Error('财务期间无效');
 if(v.revenue_scope!=null&&(typeof v.revenue_scope!=='string'||v.revenue_scope.length>300))throw Error('收入口径无效');
 const summary_hash=await hash(v.summary);return {...v,summary_hash,id:'import-'+await hash(JSON.stringify(v)),review_status:'unreviewed'};
}
