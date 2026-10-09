from __future__ import annotations
import asyncio
import json
import os
import secrets
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Annotated, Literal
from fastapi import FastAPI, HTTPException, Header, Query, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from .domain import ResearchRequest, EvidenceImport, digest, ADVICE
from .providers import ReviewedDatasetProvider, NormalizedBridgeProvider, ProviderUnavailable
from .repository import Repository
from .workflow import build_graph, UnsupportedIndustry, OutOfScope

ROOT=Path(__file__).resolve().parents[1]
@asynccontextmanager
async def lifespan(app):
    app.state.repo=Repository()
    app.state.graph=build_graph()
    yield
    app.state.repo.engine.dispose()

app=FastAPI(title="ChainScope · Industry Research",version="0.1.0",lifespan=lifespan)

def admin(authorization: Annotated[str | None, Header()]=None):
    expected=os.getenv("ADMIN_TOKEN","")
    if not expected or not secrets.compare_digest(authorization or "","Bearer "+expected):
        raise HTTPException(403,detail={"code":"WRITE_DISABLED","message":"证据写入需管理员令牌；默认禁用"})

async def dataset(request):
    provider=NormalizedBridgeProvider() if os.getenv("DATA_PROVIDER")=="bridge" else ReviewedDatasetProvider()
    try:
        d=await provider.fetch()
    except ProviderUnavailable as e:
        raise HTTPException(503,detail={"code":"PROVIDER_UNAVAILABLE","message":str(e)})
    imported=request.app.state.repo.imports(reviewed_only=True)
    for e in imported:
        d["evidence"].append(e)
        matches=[r for r in d["relations"] if all(r[k]==e[k] for k in ["company_id","node_id","route"])]
        if matches: matches[0]["evidence_ids"].append(e["id"])
        else: d["relations"].append({"id":"r-"+e["id"],"company_id":e["company_id"],"node_id":e["node_id"],"route":e["route"],"evidence_ids":[e["id"]]})
    return d

def to_http(exc):
    code="OUT_OF_SCOPE" if isinstance(exc,OutOfScope) else "UNSUPPORTED_INDUSTRY"
    return HTTPException(422,detail={"code":code,"message":str(exc)})

async def run_research(req,request):
    d=await dataset(request)
    state={"query":req.industry_name,"as_of":req.as_of.isoformat(),"route":req.route,"dataset":d,"trace":[]}
    try:
        result=await asyncio.wait_for(request.app.state.graph.ainvoke(state,{"recursion_limit":12}),timeout=35)
    except (UnsupportedIndustry,OutOfScope) as e: raise to_http(e)
    except TimeoutError: raise HTTPException(504,detail={"code":"WORKFLOW_TIMEOUT","message":"研究工作流超过时间预算"})
    report=result["final_report"]
    # Snapshot digest covers provider contents, filters and report; no global cross-request state.
    sid=digest(json.dumps(report,ensure_ascii=False,sort_keys=True))
    report["snapshot_id"]=sid
    request.app.state.repo.save_snapshot(sid,report)
    return report

@app.get("/api/v1/health")
def health():
    return {"status":"ok","backend":"FastAPI + LangGraph","provider":os.getenv("DATA_PROVIDER","reviewed_historical"),"writes_enabled":bool(os.getenv("ADMIN_TOKEN"))}

@app.post("/api/v1/research/industry")
async def research(req:ResearchRequest,request:Request): return await run_research(req,request)

@app.post("/api/v1/research/industry/stream")
async def stream(req:ResearchRequest,request:Request):
    # Validate the query before emitting SSE headers so error status remains meaningful.
    if ADVICE.search(req.industry_name): raise to_http(OutOfScope("不提供买卖建议或目标价"))
    d=await dataset(request)
    if req.industry_name.lower() not in [x.lower() for x in d["meta"]["aliases"]]: raise to_http(UnsupportedIndustry("仅支持已核验的固态电池样本"))
    async def events():
        state={"query":req.industry_name,"as_of":req.as_of.isoformat(),"route":req.route,"dataset":d,"trace":[]}
        try:
            async with asyncio.timeout(35):
                async for update in request.app.state.graph.astream(state,{"recursion_limit":12},stream_mode="updates"):
                    for node,patch in update.items():
                        yield "event: node\ndata: "+json.dumps({"node":node,"status":"ok"})+"\n\n"
                        if "final_report" in patch:
                            report=patch["final_report"]
                            sid=digest(json.dumps(report,ensure_ascii=False,sort_keys=True));report["snapshot_id"]=sid
                            request.app.state.repo.save_snapshot(sid,report)
                            yield "event: result\ndata: "+json.dumps(report,ensure_ascii=False)+"\n\n"
        except TimeoutError:
            yield 'event: error\ndata: {"code":"WORKFLOW_TIMEOUT"}\n\n'
    return StreamingResponse(events(),media_type="text/event-stream",headers={"Cache-Control":"no-cache"})

@app.get("/api/v1/research/transmission")
async def transmission(request:Request,industry:str=Query(min_length=1,max_length=100),event:str=Query(min_length=1,max_length=120),as_of:date=date(2025,3,1),route:Literal["all","all_solid","semi_solid","condensed","solid_separator"]="all",price_change:float=Query(-.2,ge=-1,le=1),material_share:float=Query(.3,ge=0,le=1),pass_through:float=Query(.7,ge=0,le=1)):
    from .domain import scenario_sensitivity
    report=await run_research(ResearchRequest(industry_name=industry,as_of=as_of,route=route),request)
    d=await dataset(request)
    scenario=next((s for s in d["scenarios"] if event in [s["event"],s["id"]]),None)
    if ADVICE.search(event): raise to_http(OutOfScope("不提供投资建议"))
    if scenario is None: raise HTTPException(422,detail={"code":"UNSUPPORTED_EVENT","message":"仅支持已定义的三种情景，不会把未知事件套入模板"})
    from .domain import eligible_paths
    paths=eligible_paths(d,report,scenario)
    return {**scenario,"paths":paths,"as_of":as_of,"claim_type":"scenario_inference","event_verified":False,
            "sensitivity":{"price_change":price_change,"material_share":material_share,"pass_through":pass_through,"baseline_revenue_contribution_pp":scenario_sensitivity(price_change,material_share,pass_through),"label":"固定销量与基期收入的毛利额贡献示意，不是公司毛利率预测"} if scenario["kind"]=="cost" else None}

@app.get("/api/v1/research/snapshots")
def snapshots(request:Request): return request.app.state.repo.snapshots()

@app.get("/api/v1/research/snapshots/{snapshot_id}")
def snapshot(snapshot_id:str,request:Request):
    value=request.app.state.repo.snapshot(snapshot_id)
    if value is None: raise HTTPException(404,detail={"code":"SNAPSHOT_NOT_FOUND"})
    return value

@app.post("/api/v1/evidence",status_code=202,dependencies=[])
async def import_evidence(payload:EvidenceImport,request:Request,authorization:Annotated[str|None,Header()]=None):
    admin(authorization)
    value=payload.model_dump(mode="json")
    value["summary_hash"]=digest(value["summary"])
    id=digest(json.dumps(value,sort_keys=True,ensure_ascii=False))
    value.update(id=id,review_status="unreviewed")
    created=request.app.state.repo.import_evidence(id,value)
    return {"id":id,"created":created,"review_status":"unreviewed","message":"导入不提升评级；需审阅后才能作为证据"}

@app.get("/api/v1/evidence/pending")
def pending(request:Request,authorization:Annotated[str|None,Header()]=None):
    admin(authorization);return request.app.state.repo.imports()

@app.post("/api/v1/evidence/{evidence_id}/review")
def review(evidence_id:str,request:Request,authorization:Annotated[str|None,Header()]=None):
    admin(authorization)
    if not request.app.state.repo.review(evidence_id): raise HTTPException(404,detail="Evidence not found")
    return {"id":evidence_id,"review_status":"reviewed"}

app.mount("/",StaticFiles(directory=ROOT/"dist",html=True),name="frontend")
