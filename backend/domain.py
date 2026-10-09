"""Deterministic fact gate shared by API and LangGraph nodes."""
from __future__ import annotations
import hashlib
import calendar
import math
import re
from datetime import date
from typing import Literal
from urllib.parse import urlparse
from pydantic import BaseModel, Field, ConfigDict, field_validator

ROUTES = Literal["all_solid", "semi_solid", "condensed", "solid_separator"]
NODES = {"lithium", "electrolyte", "cell", "process", "vehicle"}
COMPANIES = {"ganfeng", "catl", "qs", "sldp", "idemitsu", "toyota"}
OFFICIAL_DOMAINS = {"sec.gov", "www.sec.gov", "global.toyota", "www.catl.com", "www.ganfenglithium.com", "www.quantumscape.com", "www.solidpowerbattery.com", "ir.solidpowerbattery.com"}
ADVICE = re.compile(r"买入|卖出|目标价|推荐股票|必涨|稳赚|buy\s+or\s+sell|price\s+target", re.I)

class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    industry_name: str = Field(min_length=1, max_length=100)
    as_of: date = date(2025, 3, 1)
    route: Literal["all", "all_solid", "semi_solid", "condensed", "solid_separator"] = "all"

    @field_validator("industry_name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("industry_name cannot be blank")
        return value.strip()

class EvidenceImport(BaseModel):
    """Imported records cannot self-assert reviewed/verified status."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    company_id: str
    node_id: str
    route: ROUTES
    title: str = Field(min_length=2, max_length=200)
    url: str = Field(max_length=2000)
    published_at: date
    kind: Literal["revenue", "research", "statement", "rumor"]
    summary: str = Field(min_length=10, max_length=3000)
    locator: str = Field(min_length=2, max_length=300)
    source_type: Literal["annual_report", "official_material", "news"]
    revenue_amount: float | None = Field(default=None, gt=0)
    currency: Literal["CNY", "USD", "JPY", "HKD"] | None = None
    period: str | None = Field(default=None, pattern=r"^\d{4}(Q[1-4])?$")
    revenue_scope: str | None = Field(default=None, max_length=300)

    @field_validator("company_id")
    @classmethod
    def company_exists(cls, value):
        if value not in COMPANIES:
            raise ValueError("Unknown company_id")
        return value

    @field_validator("node_id")
    @classmethod
    def node_exists(cls, value):
        if value not in NODES:
            raise ValueError("Unknown node_id")
        return value

    @field_validator("url")
    @classmethod
    def safe_url(cls, value):
        p = urlparse(value)
        if p.scheme != "https" or not p.hostname or p.username or p.password:
            raise ValueError("A public HTTPS source URL is required")
        if p.hostname not in OFFICIAL_DOMAINS:
            raise ValueError("Source domain is not in the reviewed publisher allowlist")
        return value

    @field_validator("published_at")
    @classmethod
    def not_future(cls, value):
        if value > date.today():
            raise ValueError("Future publication date")
        return value

def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def valid_revenue_period(e,as_of):
    try:
        period=e["period"]
        if not re.fullmatch(r"\d{4}(Q[1-4])?",period): return False
        year=int(period[:4]);month=int(period[-1])*3 if "Q" in period else 12
        end=date(year,month,calendar.monthrange(year,month)[1])
        return end<=date.fromisoformat(e["published_at"]) and end<=as_of
    except (KeyError,ValueError,TypeError): return False

def grade_relation(relation, evidence, as_of: date):
    """Grade a relationship, never a company as a whole. Age is independent."""
    matching = [e for e in evidence if e["id"] in relation["evidence_ids"]
                and e["company_id"] == relation["company_id"]
                and e["node_id"] == relation["node_id"] and e["route"] == relation["route"]
                and date.fromisoformat(e["published_at"]) <= as_of]
    usable = [e for e in matching if e.get("review_status") == "reviewed"
              and e.get("summary_hash") == digest(e["summary"])
              and e.get("locator") and urlparse(e.get("url", "")).hostname in OFFICIAL_DOMAINS]
    level, reason, decision, financial = "M", "没有通过核验的同口径证据", "unsupported", None
    if any(e.get("conflicted") for e in usable):
        reason, decision = "存在互相矛盾的证据，需人工复核", "conflicted"
    else:
        for candidate, kinds, explanation in [
            ("A", {"revenue"}, "财报披露同口径已实现收入；不代表量产规模或投资价值"),
            ("B", {"research"}, "有研发、送样、中试或产线证据；未确认独立业务收入"),
            ("C", {"statement"}, "仅支持业务计划或未来表态，未验证对应收入"),
            ("D", {"rumor"}, "仅有市场传闻，不能作为公司已开展业务的依据"),
        ]:
            candidates = [e for e in usable if e["kind"] in kinds]
            if candidate == "A":
                candidates = [e for e in candidates if e["source_type"] == "annual_report"
                              and math.isfinite(e.get("revenue_amount") or 0) and e.get("revenue_amount", 0) > 0 and e.get("currency")
                              and e.get("period") and e.get("revenue_scope")
                              and valid_revenue_period(e,as_of)]
            if candidates:
                level, reason, decision = candidate, explanation, "supported" if candidate != "D" else "unsupported"
                if candidate == "A":
                    e = candidates[0]
                    financial = {k: e.get(k) for k in ["revenue_amount", "currency", "period", "revenue_scope", "amount_is_rounded"]}
                    financial["revenue_share"] = None  # Never infer a share from consolidated revenue.
                break
    return {**relation, "evidence_level": level, "grade_reason": reason,
            "decision": decision, "financial": financial,
            "citation_source": [{k: e.get(k) for k in ["id", "title", "url", "locator", "published_at", "summary", "summary_hash", "review_status"]} for e in usable],
            "stale": bool(usable) and all((date.today()-date.fromisoformat(e["published_at"])).days > 365 for e in usable),
            "missing_reason": None if usable else "无可用证据；不等于事实上的零收入"}

def scenario_sensitivity(price_change: float, material_share: float, pass_through: float):
    """Fixed-volume, fixed-baseline-revenue contribution; deliberately not company guidance."""
    if not (-1 <= price_change <= 1 and 0 <= material_share <= 1 and 0 <= pass_through <= 1):
        raise ValueError("Scenario parameters out of range")
    return round(-price_change * material_share * (1-pass_through) * 100, 4)

def eligible_paths(dataset,report,scenario):
    """Keep each company's supported contribution rather than dropping its peers."""
    supported={e["id"] for r in report["evidence_graph"] if r["decision"]=="supported" for e in r["citation_source"]}
    entities={e["id"]:e["company_id"] for e in dataset["evidence"]}
    paths=[]
    for p in scenario["paths"]:
        per_company={cid:[eid for eid in p["evidence_ids"] if entities.get(eid)==cid] for cid in p["company_ids"]}
        selected=[cid for cid,ids in per_company.items() if ids and set(ids)<=supported]
        if selected:
            paths.append({**p,"company_ids":selected,"evidence_ids":[eid for eid in p["evidence_ids"] if entities.get(eid) in selected],"claim_type":"scenario_inference","numeric_impact":None})
    return paths
