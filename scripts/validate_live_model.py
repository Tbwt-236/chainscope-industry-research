"""Run a real model selection through LangGraph; never record API keys.

Usage: python scripts/validate_live_model.py --output docs/live_model_validation.json
Reads optional local .env. Exits 2 when credentials are absent or a model falls back.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.workflow import build_graph

def load_local_env():
    file=ROOT/".env"
    if file.exists():
        for line in file.read_text().splitlines():
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            key,value=line.split("=",1)
            if key.strip() in {"LLM_BASE_URL","LLM_API_KEY","LLM_MODEL"} and not os.getenv(key.strip()):
                os.environ[key.strip()]=value.strip().strip('"').strip("'")

async def validate():
    load_local_env()
    configured={k:bool(os.getenv(k)) for k in ["LLM_BASE_URL","LLM_API_KEY","LLM_MODEL"]}
    proof={"checked_at":datetime.now(timezone.utc).isoformat(),"configured":configured,"real_model_verified":False,"test_type":"live_integration"}
    if not all(configured.values()): return {**proof,"status":"not_configured","reason":"Missing local model configuration; no request sent"}
    parsed=urlparse(os.getenv("LLM_BASE_URL",""))
    if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password:
        return {**proof,"status":"invalid_configuration","reason":"Use an HTTPS API base URL without embedded credentials"}
    data=json.loads((ROOT/"data/research.json").read_text())
    started=time.monotonic()
    state=await build_graph().ainvoke({"query":"固态电池","as_of":"2025-03-01","route":"all","dataset":data,"trace":[]},{"recursion_limit":12})
    report=state["final_report"]
    expected={e["id"]:e["summary"] for e in data["evidence"]}
    valid=all(len(c["evidence_ids"])==1 and expected.get(c["evidence_ids"][0])==c["text"] for c in report["claims"])
    success=report["ai_mode"]=="llm_selected" and valid and bool(report["claims"])
    return {**proof,"status":"passed" if success else "fallback","real_model_verified":success,
            "endpoint_host":parsed.hostname,"model":os.getenv("LLM_MODEL"),"elapsed_seconds":round(time.monotonic()-started,3),
            "ai_mode":report["ai_mode"],"input_evidence_ids":list(expected),"selected_evidence_ids":[i for c in report["claims"] for i in c["evidence_ids"]],
            "all_claims_reconstructed_from_reviewed_records":valid,"workflow_nodes":[n["node"] for n in report["trace"]],"warnings":report["warnings"]}

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path);args=parser.parse_args()
    proof=asyncio.run(validate())
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(proof,ensure_ascii=False))
    raise SystemExit(0 if proof["real_model_verified"] else 2)
