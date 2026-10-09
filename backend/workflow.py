from __future__ import annotations
import operator
from datetime import date
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from .domain import grade_relation, ADVICE
from .providers import select_evidence

class UnsupportedIndustry(ValueError): pass
class OutOfScope(ValueError): pass
class ResearchState(TypedDict, total=False):
    query: str
    as_of: str
    route: str
    dataset: dict
    industry_context: dict
    companies: list
    evidence_graph: list
    comparisons: list
    transmission: list
    final_report: dict
    trace: Annotated[list,operator.add]

def intent_parser(s):
    if ADVICE.search(s["query"]): raise OutOfScope("不提供买卖建议、目标价或确定性收益预测")
    if s["query"].strip().lower() not in [v.lower() for v in s["dataset"]["meta"]["aliases"]]:
        raise UnsupportedIndustry("当前已核验数据集仅覆盖固态电池；不会用其他产业的样本冒充结果")
    return {"industry_context":s["dataset"]["meta"],"trace":[{"node":"IntentParser","status":"ok"}]}

def industry_structurer(s):
    return {"trace":[{"node":"IndustryStructurer","status":"ok","taxonomy":s["dataset"]["meta"]["taxonomy"]}]}

def company_locator(s):
    d=s["dataset"]
    relations=[r for r in d["relations"] if s.get("route","all")=="all" or r["route"]==s["route"]]
    graded=[grade_relation(r,d["evidence"],date.fromisoformat(s["as_of"])) for r in relations]
    companies=[{**c,"relations":[r for r in graded if r["company_id"]==c["id"]]} for c in d["companies"] if any(r["company_id"]==c["id"] for r in graded)]
    return {"companies":companies,"evidence_graph":graded,"trace":[{"node":"CompanyLocatorEvidenceGrader","status":"ok","relationships":len(graded)}]}

def comparator(s):
    # Only render comparisons whose every factual basis passed the same as-of gate.
    supported={e["id"] for r in s["evidence_graph"] if r["decision"]=="supported" for e in r["citation_source"]}
    ids={c["id"] for c in s["companies"]}
    comparisons=[{**c,"claim_type":"analyst_inference"} for c in s["dataset"]["comparisons"] if c["left"] in ids and c["right"] in ids and set(c["evidence_ids"])<=supported]
    return {"comparisons":comparisons,"trace":[{"node":"CrossMarketComparator","status":"ok"}]}

def transmission_tracer(s):
    return {"transmission":[{"id":x["id"],"event":x["event"]} for x in s["dataset"]["scenarios"]],"trace":[{"node":"TransmissionTracer","status":"scenario_catalog"}]}

async def report_gate(s):
    supported={e["id"] for r in s["evidence_graph"] if r["decision"]=="supported" for e in r["citation_source"]}
    evidence=[e for e in s["dataset"]["evidence"] if e["id"] in supported]
    selected,mode,warning=await select_evidence(evidence)
    # The model cannot write assertions. Report facts are reconstructed from reviewed records.
    by_id={e["id"]:e for e in evidence}
    facts=[{"text":by_id[i]["summary"],"evidence_ids":[i],"decision":"supported"} for i in selected]
    result={"meta":s["industry_context"],"as_of":s["as_of"],"route":s["route"],
            "hierarchy":s["dataset"]["nodes"],"edges":s["dataset"]["edges"],
            "companies":s["companies"],"evidence_graph":s["evidence_graph"],"comparisons":s["comparisons"],
            "transmission_events":s["transmission"],"claims":facts,"ai_mode":mode,
            "warnings":[warning] if warning else [],"trace":s["trace"]+[{"node":"ReportGate","status":"ok"}],
            "boundary":"研究辅助；不提供买卖建议或目标价。情景推演不是已发生的财务事实。"}
    return {"final_report":result,"trace":[{"node":"ReportGate","status":"ok"}]}

def build_graph():
    g=StateGraph(ResearchState)
    steps=[("IntentParser",intent_parser),("IndustryStructurer",industry_structurer),
           ("CompanyLocatorEvidenceGrader",company_locator),("CrossMarketComparator",comparator),
           ("TransmissionTracer",transmission_tracer),("ReportGate",report_gate)]
    prev=START
    for name,fn in steps:
        g.add_node(name,fn);g.add_edge(prev,name);prev=name
    g.add_edge(prev,END)
    return g.compile()  # No persistent checkpointer required for this bounded DAG.
