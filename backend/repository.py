from __future__ import annotations
import os
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, String, Text, JSON, DateTime, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.exc import IntegrityError

ROOT=Path(__file__).resolve().parents[1]
class Base(DeclarativeBase): pass

class Snapshot(Base):
    __tablename__="research_snapshots"
    id: Mapped[str]=mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))
    payload: Mapped[dict]=mapped_column(JSON)

class ImportedEvidence(Base):
    __tablename__="imported_evidence"
    id: Mapped[str]=mapped_column(String(64), primary_key=True)
    payload: Mapped[dict]=mapped_column(JSON)
    review_status: Mapped[str]=mapped_column(String(20), default="unreviewed")

class Repository:
    def __init__(self,url=None):
        (ROOT/"runtime").mkdir(exist_ok=True)
        url=url or os.getenv("DATABASE_URL",f"sqlite:///{ROOT/'runtime/research.db'}")
        self.engine=create_engine(url,connect_args={"check_same_thread":False} if url.startswith("sqlite") else {}, pool_pre_ping=True)
        self.session=sessionmaker(self.engine)
        Base.metadata.create_all(self.engine)

    def save_snapshot(self,id,payload):
        try:
            with self.session.begin() as s:
                if s.get(Snapshot,id) is None:
                    s.add(Snapshot(id=id,payload=payload))
        except IntegrityError:
            with self.session() as s:
                if s.get(Snapshot,id) is None: raise

    def snapshots(self):
        with self.session() as s:
            return [{"id":r.id,"created_at":r.created_at.isoformat(),"data_version":r.payload["meta"]["version"],"as_of":r.payload["as_of"]} for r in s.scalars(select(Snapshot).order_by(Snapshot.created_at.desc()).limit(50))]

    def snapshot(self,id):
        with self.session() as s:
            row=s.get(Snapshot,id)
            return row.payload if row else None

    def import_evidence(self,id,payload):
        try:
            with self.session.begin() as s:
                if s.get(ImportedEvidence,id): return False
                s.add(ImportedEvidence(id=id,payload=payload))
        except IntegrityError:
            with self.session() as s:
                if s.get(ImportedEvidence,id) is None: raise
                return False
        return True

    def imports(self, reviewed_only=False):
        with self.session() as s:
            rows=s.scalars(select(ImportedEvidence)).all()
            return [{**r.payload,"review_status":r.review_status} for r in rows if not reviewed_only or r.review_status=="reviewed"]

    def review(self,id):
        with self.session.begin() as s:
            row=s.get(ImportedEvidence,id)
            if row is None: return False
            row.review_status="reviewed"
            row.payload={**row.payload,"reviewed_at":datetime.now(timezone.utc).date().isoformat()}
            return True
