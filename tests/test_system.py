import asyncio
import copy
import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.domain import grade_relation,digest,scenario_sensitivity
from backend.main import app
from backend.providers import NormalizedBridgeProvider,ProviderUnavailable,select_evidence,validate_dataset

ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture
def data(): return json.loads((ROOT/"data/research.json").read_text())

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv("DATABASE_URL",f"sqlite:///{tmp_path/'test.db'}")
    for k in ["ADMIN_TOKEN","LLM_API_KEY","LLM_BASE_URL","LLM_MODEL","DATA_PROVIDER"]: monkeypatch.delenv(k,raising=False)
    with TestClient(app) as c: yield c

def grade(data,index=0,as_of="2025-03-01"):
    return grade_relation(data["relations"][index],data["evidence"],date.fromisoformat(as_of))

def test_real_revenue_is_scoped(data):
    result=grade(data)
    assert result["evidence_level"]=="A"
    assert result["financial"]["revenue_amount"]==11800000
    assert "技术转移" in result["financial"]["revenue_scope"]
    assert result["financial"]["revenue_share"] is None

def test_one_company_has_different_relationship_grades(data):
    assert grade(data,0)["evidence_level"]=="A"
    assert grade(data,1)["evidence_level"]=="B"

@pytest.mark.parametrize("missing",["revenue_amount","period","currency","revenue_scope"])
def test_missing_financial_field_blocks_a(data,missing):
    data["evidence"][0].pop(missing)
    assert grade(data)["evidence_level"]=="M"

def test_research_stays_b_without_financials(data):
    assert grade(data,1)["evidence_level"]=="B"

@pytest.mark.parametrize("amount",[0,-1,float('inf'),float('nan')])
def test_nonpositive_nonfinite_revenue_blocked(data,amount):
    data['evidence'][0]['revenue_amount']=amount
    assert grade(data)['evidence_level']=='M'

def test_future_financial_period_blocked(data):
    data['evidence'][0]['period']='2025'
    assert grade(data)['evidence_level']=='M'

@pytest.mark.parametrize("field,value",[("company_id","qs"),("node_id","cell"),("route","semi_solid")])
def test_context_mismatch_blocks(data,field,value):
    data["evidence"][0][field]=value
    assert grade(data)["evidence_level"]=="M"

def test_tampered_summary_blocks(data):
    data["evidence"][0]["summary"]+=" 已量产电芯"
    assert grade(data)["evidence_level"]=="M"

def test_future_evidence_excluded(data):
    assert grade(data,0,"2024-12-31")["evidence_level"]=="M"

def test_missing_does_not_become_zero(data):
    data["evidence"]=[]
    r=grade(data)
    assert r["evidence_level"]=="M" and r["financial"] is None

def test_conflict_preserved(data):
    data["evidence"][0]["conflicted"]=True
    assert grade(data)["decision"]=="conflicted"

def test_plan_is_c(data): assert grade(data,6)["evidence_level"]=="C"

def test_rumor_never_business_proof(data):
    data["evidence"][6]["kind"]="rumor"
    r=grade(data,6)
    assert r["evidence_level"]=="D" and r["decision"]=="unsupported"

def test_unreviewed_cannot_upgrade(data):
    data["evidence"][0]["review_status"]="unreviewed"
    assert grade(data)["evidence_level"]=="M"

def test_complete_workflow_and_snapshot(client):
    body=client.post('/api/v1/research/industry',json={"industry_name":"固态电池"}).json()
    assert len(body['companies'])==6 and len(body['evidence_graph'])==7
    assert [n['node'] for n in body['trace']]==['IntentParser','IndustryStructurer','CompanyLocatorEvidenceGrader','CrossMarketComparator','TransmissionTracer','ReportGate']
    assert len(body['comparisons'])==2
    assert body['ai_mode']=='deterministic'
    sid=body['snapshot_id']
    assert client.get('/api/v1/research/snapshots/'+sid).json()==body
    assert client.post('/api/v1/research/industry',json={"industry_name":"固态电池"}).json()['snapshot_id']==sid
    assert len(client.get('/api/v1/research/snapshots').json())==1

@pytest.mark.parametrize("query",["算力网络","固态电池买入建议","固态电池目标价"," "])
def test_invalid_or_out_of_scope_rejected(client,query):
    assert client.post('/api/v1/research/industry',json={"industry_name":query}).status_code==422

def test_asof_gates_comparison_and_transmission(client):
    body=client.post('/api/v1/research/industry',json={"industry_name":"固态电池","as_of":"2023-01-01"}).json()
    assert all(r['evidence_level']=='M' for r in body['evidence_graph'])
    assert not body['comparisons']
    result=client.get('/api/v1/research/transmission',params={"industry":"固态电池","event":"全固态量产延期","as_of":"2023-01-01"}).json()
    assert not result['paths']

def test_tech_filter_excludes_neighbors(client):
    body=client.post('/api/v1/research/industry',json={"industry_name":"固态电池","route":"all_solid"}).json()
    assert all(r['route']=='all_solid' for r in body['evidence_graph'])
    assert all(c['id'] not in ['ganfeng','catl','qs'] for c in body['companies'])

def test_transmission_is_conditional(client):
    r=client.get('/api/v1/research/transmission',params={"industry":"固态电池","event":"碳酸锂价格下跌"})
    assert r.status_code==200
    body=r.json()
    assert body['event_verified'] is False
    assert body['sensitivity']['baseline_revenue_contribution_pp']==1.8
    assert all(p['assumptions'] and p['counter'] and p['numeric_impact'] is None for p in body['paths'])

def test_transmission_respects_technical_filter(client):
    body=client.get('/api/v1/research/transmission',params={'industry':'固态电池','event':'碳酸锂价格下跌','route':'all_solid'}).json()
    assert all('ganfeng' not in p['company_ids'] for p in body['paths'])

@pytest.mark.parametrize("params",[{"event":"外星冲击"},{"event":"目标价"},{"event":"碳酸锂价格下跌","pass_through":1.1}])
def test_invalid_transmission_rejected(client,params):
    assert client.get('/api/v1/research/transmission',params={"industry":"固态电池",**params}).status_code==422

def imported_payload(data):
    return {k:v for k,v in data['evidence'][0].items() if k in ['company_id','node_id','route','title','url','published_at','kind','summary','locator','source_type','revenue_amount','currency','period','revenue_scope']}

def test_writes_disabled_by_default(client,data):
    assert client.post('/api/v1/evidence',json=imported_payload(data)).status_code==403

def test_import_is_idempotent_and_requires_review(client,data,monkeypatch):
    monkeypatch.setenv('ADMIN_TOKEN','unit-test-token')
    h={'Authorization':'Bearer unit-test-token'}
    p=imported_payload(data)
    p.update(company_id='qs',node_id='cell',route='solid_separator',summary='测试夹具：假设财报明确披露技术许可收入；仅用于验证人工审核流程，不是实际公司事实。')
    res=client.post('/api/v1/evidence',json=p,headers=h)
    assert res.status_code==202 and res.json()['review_status']=='unreviewed'
    assert client.post('/api/v1/evidence',json=p,headers=h).json()['created'] is False
    before=client.post('/api/v1/research/industry',json={'industry_name':'固态电池'}).json()
    assert next(r for r in before['evidence_graph'] if r['company_id']=='qs')['evidence_level']=='B'
    assert client.post('/api/v1/evidence/'+res.json()['id']+'/review',headers=h).status_code==200
    after=client.post('/api/v1/research/industry',json={'industry_name':'固态电池'}).json()
    assert next(r for r in after['evidence_graph'] if r['company_id']=='qs')['evidence_level']=='A'
    assert before['snapshot_id']!=after['snapshot_id']

@pytest.mark.parametrize('mutation',[{'review_status':'reviewed'},{'url':'http://127.0.0.1/private'},{'revenue_amount':-1},{'company_id':'fake'},{'published_at':'2099-01-01'}])
def test_import_schema_validation(client,data,monkeypatch,mutation):
    monkeypatch.setenv('ADMIN_TOKEN','test')
    assert client.post('/api/v1/evidence',json={**imported_payload(data),**mutation},headers={'Authorization':'Bearer test'}).status_code==422

def test_sse_returns_real_node_events(client):
    res=client.post('/api/v1/research/industry/stream',json={'industry_name':'固态电池'})
    assert res.status_code==200 and 'text/event-stream' in res.headers['content-type']
    assert res.text.count('event: node')==6 and 'event: result' in res.text

def test_missing_snapshot_404(client): assert client.get('/api/v1/research/snapshots/missing').status_code==404

def test_calculator_boundaries():
    assert scenario_sensitivity(-.2,.3,0)==6
    assert scenario_sensitivity(-.2,.3,1)==0
    assert scenario_sensitivity(.2,.3,.7)==-1.8
    with pytest.raises(ValueError): scenario_sensitivity(-2,.3,.7)

def test_llm_unknown_ids_blocked(data,monkeypatch):
    for k,v in [('LLM_API_KEY','test'),('LLM_BASE_URL','https://test.invalid/v1'),('LLM_MODEL','test')]:monkeypatch.setenv(k,v)
    response=httpx.Response(200,json={'choices':[{'message':{'content':'{"evidence_ids":["invented-source"],"claims":["必涨100%"]}'}}]},request=httpx.Request('POST','https://test.invalid'))
    fake=AsyncMock();fake.post.return_value=response
    fake.__aenter__.return_value=fake
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:fake)
    ids,mode,warning=asyncio.run(select_evidence(data['evidence']))
    assert mode=='deterministic_fallback' and 'invented-source' not in ids and warning

def test_provider_timeout_returns_503(client,monkeypatch):
    monkeypatch.setenv('DATA_PROVIDER','bridge');monkeypatch.setenv('DATA_BRIDGE_URL','https://test.invalid')
    fake=AsyncMock();fake.get.side_effect=httpx.ReadTimeout('timeout');fake.__aenter__.return_value=fake
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:fake)
    monkeypatch.setattr('backend.providers.asyncio.sleep',AsyncMock())
    res=client.post('/api/v1/research/industry',json={'industry_name':'固态电池'})
    assert res.status_code==503 and res.json()['detail']['code']=='PROVIDER_UNAVAILABLE'
    assert fake.get.await_count==2

def test_provider_malformed_data_returns_503(client,monkeypatch):
    monkeypatch.setenv('DATA_PROVIDER','bridge');monkeypatch.setenv('DATA_BRIDGE_URL','https://test.invalid')
    response=httpx.Response(200,json={'meta':[],'nodes':[],'companies':[],'relations':[],'evidence':[],'comparisons':[],'scenarios':[]},request=httpx.Request('GET','https://test.invalid'))
    fake=AsyncMock();fake.get.return_value=response;fake.__aenter__.return_value=fake
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:fake)
    monkeypatch.setattr('backend.providers.asyncio.sleep',AsyncMock())
    assert client.post('/api/v1/research/industry',json={'industry_name':'固态电池'}).status_code==503

@pytest.mark.parametrize('fault',['missing_edges','invalid_edges','unknown_evidence','invalid_date','missing_title','tampered_hash'])
def test_bridge_rejects_nested_contract_faults(client,data,monkeypatch,fault):
    if fault=='missing_edges': data.pop('edges')
    if fault=='invalid_edges': data['edges']=[['lithium','unknown']]
    if fault=='unknown_evidence': data['relations'][0]['evidence_ids']=['unknown']
    if fault=='invalid_date': data['evidence'][0]['published_at']='not-a-date'
    if fault=='missing_title': data['evidence'][0].pop('title')
    if fault=='tampered_hash': data['evidence'][0]['summary_hash']='fake'
    monkeypatch.setenv('DATA_PROVIDER','bridge');monkeypatch.setenv('DATA_BRIDGE_URL','https://test.invalid')
    response=httpx.Response(200,json=data,request=httpx.Request('GET','https://test.invalid'))
    fake=AsyncMock();fake.get.return_value=response;fake.__aenter__.return_value=fake
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:fake)
    monkeypatch.setattr('backend.providers.asyncio.sleep',AsyncMock())
    r=client.post('/api/v1/research/industry',json={'industry_name':'固态电池'})
    assert r.status_code==503 and r.json()['detail']['code']=='PROVIDER_UNAVAILABLE'

def test_bridge_records_cannot_self_review(data):
    assert all(e['review_status']=='unreviewed' for e in validate_dataset(data)['evidence'])

@pytest.mark.parametrize('route,expected',[('all_solid',['sldp']),('solid_separator',['qs'])])
def test_transmission_keeps_supported_company_when_peer_filtered(client,route,expected):
    body=client.get('/api/v1/research/transmission',params={'industry':'固态电池','event':'全固态量产延期','route':route}).json()
    p=next(p for p in body['paths'] if p['node_id']=='process')
    assert p['company_ids']==expected
    assert p['evidence_ids']==(['e-sldp-revenue'] if route=='all_solid' else ['e-qs'])

def test_llm_valid_selection_cannot_inject_free_form_facts(client,data,monkeypatch):
    for k,v in [('LLM_API_KEY','test'),('LLM_BASE_URL','https://test.invalid/v1'),('LLM_MODEL','test')]:monkeypatch.setenv(k,v)
    response=httpx.Response(200,json={'choices':[{'message':{'content':'{"evidence_ids":["e-qs"],"claims":["虚构盈利100%"]}'}}]},request=httpx.Request('POST','https://test.invalid'))
    fake=AsyncMock();fake.post.return_value=response;fake.__aenter__.return_value=fake
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:fake)
    report=client.post('/api/v1/research/industry',json={'industry_name':'固态电池'}).json()
    assert report['ai_mode']=='llm_selected'
    assert report['claims']==[{'text':data['evidence'][2]['summary'],'evidence_ids':['e-qs'],'decision':'supported'}]

def test_real_update_sample_requires_review_and_later_cutoff(client,monkeypatch):
    monkeypatch.setenv('ADMIN_TOKEN','update-test')
    headers={'Authorization':'Bearer update-test'}
    sample=json.loads((ROOT/'data/update-sample.json').read_text())
    added=client.post('/api/v1/evidence',json=sample,headers=headers)
    assert added.status_code==202
    def qs(as_of):
        report=client.post('/api/v1/research/industry',json={'industry_name':'固态电池','as_of':as_of}).json()
        return next(r for r in report['evidence_graph'] if r['company_id']=='qs')
    assert len(qs('2026-02-25')['citation_source'])==1
    assert client.post('/api/v1/evidence/'+added.json()['id']+'/review',headers=headers).status_code==200
    assert len(qs('2025-03-01')['citation_source'])==1
    current=qs('2026-02-25')
    assert current['evidence_level']=='B' and current['financial'] is None
    assert len(current['citation_source'])==2
