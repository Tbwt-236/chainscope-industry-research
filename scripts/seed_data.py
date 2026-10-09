"""Build a small, reviewed historical research dataset; no live-data claim."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def source(id, company, node, title, url, date, kind, route, summary, locator, **extra):
    return dict(id=id, company_id=company, node_id=node, title=title, url=url,
                published_at=date, retrieved_at="2026-10-09", reviewed_at="2026-10-09",
                review_status="reviewed", source_type="annual_report" if kind=="revenue" else "official_material",
                kind=kind, route=route, summary=summary, locator=locator,
                summary_hash=hashlib.sha256(summary.encode()).hexdigest(), **extra)

sldp="https://www.sec.gov/Archives/edgar/data/1844862/000155837025001874/sldp-20241231x10k.htm"
toyota="https://global.toyota/en/newsroom/corporate/39865919.html"
sources=[
source("e-sldp-revenue","sldp","process","Solid Power 2024 Form 10-K",sldp,"2025-02-28","revenue","all_solid",
       "2024 年 SK On 协议项下的产线安装与技术转移合计贡献约 1,180 万美元收入。属于固态电池技术服务，不能解释为量产电芯或电解质销售收入。",
       "Item 7 · Revenue（年报第 36 页）",revenue_amount=11800000,currency="USD",period="2024",revenue_scope="固态电池产线安装与技术转移服务",amount_is_rounded=True),
source("e-sldp-rd","sldp","electrolyte","Solid Power 2024 Form 10-K",sldp,"2025-02-28","research","all_solid",
       "报告说明公司开展硫化物固态电解质研发与客户送样，商业模式包括电解质供货和技术许可。中试及送样证据不能直接证明规模销售。",
       "Item 1 · 2024 Business Highlights / Partnerships"),
source("e-qs","qs","cell","QuantumScape 2024 Form 10-K",
       "https://www.sec.gov/Archives/edgar/data/1811414/000095017025027308/qs-20241231.htm",
       "2025-02-26","research","solid_separator",
       "年报披露 B 样品送测及陶瓷固态隔膜平台；现有原型正极含有机液态电解液。与 PowerCo 合作采用许可模式，不能把其“固态”直接等同全固态电芯。",
       "Item 1 · Our Technology / Our Cells and Separator / PowerCo"),
source("e-idemitsu","idemitsu","electrolyte","出光与丰田：全固态电池量产合作",toyota,"2023-10-12","research","all_solid",
       "双方合作开发硫化物固态电解质，推进中试与量产工艺。披露了材料与制造职责，并未给出固态电解质业务独立收入。",
       "Details of collaboration · Phase 1–3"),
source("e-toyota","toyota","vehicle","出光与丰田：全固态电池量产合作",toyota,"2023-10-12","research","all_solid",
       "丰田承担全固态电池及其整车集成开发。原材料中的 2027–2028 年为当时提出的商业化目标，并非已完成投产事实，需以后续公告复核。",
       "Details of collaboration · Phase 2"),
source("e-ganfeng","ganfeng","cell","赣锋锂业 2023 年度回顾",
       "https://www.ganfenglithium.com/new_detail/id/123.html","2024-01-02","research","semi_solid",
       "公司回顾披露固液混合锂离子电池交付赛力斯汽车投产。该证据支持半固态业务进展，不支持全固态电池量产结论，也没有独立收入金额。",
       "2023 年度回顾 · 固液混合锂离子电池"),
source("e-catl","catl","cell","宁德时代发布凝聚态电池",
       "https://www.catl.com/news/7140.html","2023-04-19","statement","condensed",
       "发布材料提出将推出车规级应用版本。此处仅据未来产品计划评 C；凝聚态属于相邻技术，不能据此认定全固态电池已实现业务收入。",
       "新闻发布 · 车规级版本计划")
]
data={
 "meta":{"industry":"固态电池","aliases":["固态电池","全固态电池","solid state battery","solid-state batteries"],"version":"2026-10-09.1","data_as_of":"2025-03-01","reviewed_at":"2026-10-09","mode":"reviewed_historical","notice":"历史证据样本，2026-10-09 复核来源；不代表公司最新进展。","taxonomy":"按价值链功能分层；全固态、半固态、固态隔膜和凝聚态分开标识。"},
 "nodes":[
 {"id":"lithium","stage":"上游","name":"锂源与前驱体","description":"锂盐、硫化锂等原料；不能把一般锂盐收入归入固态专属收入。","order":1},
 {"id":"electrolyte","stage":"上游","name":"固态电解质","description":"硫化物、氧化物、聚合物等技术路线；各路线并不互相等价。","order":2},
 {"id":"cell","stage":"中游","name":"电芯开发与制造","description":"材料界面、锂金属负极、成型工艺及电芯验证。","order":3},
 {"id":"process","stage":"中游","name":"工艺许可与产线工程","description":"研发许可、工艺转移和产线安装；技术服务收入与电芯销量区分。","order":4},
 {"id":"vehicle","stage":"下游","name":"整车集成与验证","description":"车端验证、供应链导入和商业化；目标日期不等于实际投产。","order":5}
 ],
 "edges":[["lithium","electrolyte"],["electrolyte","cell"],["process","cell"],["cell","vehicle"]],
 "companies":[
 {"id":"ganfeng","name":"赣锋锂业","ticker":"002460.SZ / 01772.HK","market":"CN","business":"锂资源与锂电池；本样本支持半固态交付"},
 {"id":"catl","name":"宁德时代","ticker":"300750.SZ","market":"CN","business":"动力与储能电池；本样本为凝聚态车规版本计划"},
 {"id":"qs","name":"QuantumScape","ticker":"QS · NYSE","market":"US","business":"固态锂金属电池技术与许可"},
 {"id":"sldp","name":"Solid Power","ticker":"SLDP · Nasdaq","market":"US","business":"硫化物电解质、研发许可与工程服务"},
 {"id":"idemitsu","name":"出光兴产","ticker":"5019 · TSE","market":"JP","business":"能源与材料；硫化物固态电解质开发"},
 {"id":"toyota","name":"丰田汽车","ticker":"7203 · TSE","market":"JP","business":"整车制造、全固态电池及整车集成开发"}
 ],
 "relations":[{"id":"r-"+s["id"][2:],"company_id":s["company_id"],"node_id":s["node_id"],"route":s["route"],"evidence_ids":[s["id"]]} for s in sources],
 "evidence":sources,
 "comparisons":[
 {"id":"cmp-cell","left":"ganfeng","right":"qs","title":"赣锋锂业 × QuantumScape","basis":"电芯开发与汽车导入：同环节、不同技术路线",
  "comparable":["都涉及下一代锂电芯开发与汽车客户导入，可对照研发和验证阶段。"],
  "not_comparable":["赣锋样本披露的是固液混合；QS 使用陶瓷固态隔膜，但其年报原型正极仍含液态电解液，不能将 QS 直接视为全固态。","赣锋覆盖锂资源与电池；QS 的该合作侧重技术许可。业务范围及收入基础不同，不能直接套用估值。"],
  "evidence_ids":["e-ganfeng","e-qs"],"verdict":"有限可比"},
 {"id":"cmp-material","left":"sldp","right":"idemitsu","title":"Solid Power × 出光兴产","basis":"硫化物固态电解质：同环节、相近路线",
  "comparable":["均开发硫化物固态电解质，可对照中试工艺、客户验证与扩产约束。"],
  "not_comparable":["Solid Power 还提供研发许可和产线工程，出光样本侧重材料供应及与丰田合作。","双方没有在本数据集中披露同口径的电解质收入、良率和单位成本，不能进行直接财务倍数比较。"],
  "evidence_ids":["e-sldp-rd","e-sldp-revenue","e-idemitsu"],"verdict":"技术环节可比"}
 ],
 "scenarios":[
 {"id":"lithium_down","event":"碳酸锂价格下跌","kind":"cost","summary":"成本下降沿材料与电芯环节传递；利润方向取决于库存与售价调整。",
  "paths":[
   {"node_id":"lithium","company_ids":["ganfeng"],"business_effect":"锂盐售价承压，存货账面价值可能受影响。","metrics":["锂盐业务收入","存货减值"],"direction":"承压","assumptions":["公司具有锂盐销售敞口","售价随现货或合同重定价"],"counter":"销量增加、低成本矿源及套期保值可能抵消影响。","evidence_ids":["e-ganfeng"],"evidence_limit":"来源支持公司涉及锂业务；此价格冲击及财务方向为情景推演。"},
   {"node_id":"cell","company_ids":["ganfeng"],"business_effect":"锂基材料成本可能下降；对半固态电芯的收益需看采购与售价联动。","metrics":["单位材料成本","电池业务毛利率"],"direction":"条件性改善","assumptions":["低价原料已进入生产成本","降本未被售价同步下调完全转移"],"counter":"库存成本滞后、价格竞争或良率不足可能抵消降本。","evidence_ids":["e-ganfeng"],"evidence_limit":"无公司级敏感度参数，不能量化公司盈利增幅。"},
   {"node_id":"vehicle","company_ids":["toyota"],"business_effect":"只有采购降价传导到电池包且项目商业化后，才可能改善整车成本。","metrics":["电池采购成本","整车毛利率"],"direction":"间接且滞后","assumptions":["目标电池进入商业化供货","合同允许成本下降传导"],"counter":"开发支出和验证周期可能比原料价格更重要。","evidence_ids":["e-toyota"],"evidence_limit":"全固态商业化目标不是已经产生收入的证明。"}
  ]},
 {"id":"delay","event":"全固态量产延期","kind":"schedule","summary":"假设产业化验证延后，分别观察材料订单、许可里程碑和整车导入。",
  "paths":[
   {"node_id":"electrolyte","company_ids":["sldp","idemitsu"],"business_effect":"客户验证和材料采购可能后移，研发现金消耗时间延长。","metrics":["材料订单","研发费用","经营现金流"],"direction":"回款可能延后","assumptions":["采购量与客户验证里程碑挂钩"],"counter":"研发样品或独立技术服务可能仍有收入。","evidence_ids":["e-sldp-rd","e-idemitsu"],"evidence_limit":"未确认发生延期，为用户设定情景。"},
   {"node_id":"process","company_ids":["sldp","qs"],"business_effect":"技术许可及工程里程碑交付可能延后；不能据此假定所有收入归零。","metrics":["里程碑收入确认","合同负债","现金回款"],"direction":"依合同而定","assumptions":["合同付款存在技术交付条件"],"counter":"预付款、已完成安装和独立交付任务可缓冲影响。","evidence_ids":["e-sldp-revenue","e-qs"],"evidence_limit":"需阅读对应合同才能量化。"},
   {"node_id":"vehicle","company_ids":["toyota"],"business_effect":"全固态车型导入推迟可能改变研发与设备投资节奏。","metrics":["研发费用","资本开支","项目现金流"],"direction":"投资回收后移","assumptions":["延期影响车型开发和采购计划"],"counter":"其他动力路线与车型可能补位。","evidence_ids":["e-toyota"],"evidence_limit":"不推算整车集团净利润。"}
  ]},
 {"id":"tariff","event":"电池进口关税上调","kind":"policy","summary":"先识别原产地、产品编码、贸易方向与合同，再判断跨境业务敞口。",
  "paths":[
   {"node_id":"cell","company_ids":["ganfeng"],"business_effect":"只有相关跨境电池交易实际受该税则覆盖时，到岸成本才会上升。","metrics":["到岸成本","出口订单","业务毛利率"],"direction":"需要贸易敞口确认","assumptions":["明确税区和税则编码","存在受影响的跨境交易","合同约定税费承担方"],"counter":"本地生产、豁免、转移采购或客户承担关税可减弱影响。","evidence_ids":["e-ganfeng"],"evidence_limit":"样本未含贸易敞口，不能断言公司已受影响。"},
   {"node_id":"process","company_ids":["qs","sldp"],"business_effect":"技术许可收入与实体电芯进口的税则适用可能不同。","metrics":["许可收入","合作项目资本开支"],"direction":"不直接套用电芯税率","assumptions":["分别核实技术许可与货物税则"],"counter":"合作方本地制造可改变贸易路径。","evidence_ids":["e-qs","e-sldp-revenue"],"evidence_limit":"未引用或判断任何现行关税政策；仅作机制情景。"}
  ]}
 ]
}
for p in [ROOT/"data/research.json",ROOT/"dist/research.json"]:
 p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
print("Built 6 companies, 7 relationship-scoped evidence records.")
