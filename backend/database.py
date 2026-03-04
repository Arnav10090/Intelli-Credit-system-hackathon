"""
database.py
─────────────────────────────────────────────────────────────────────────────
SQLite database layer using SQLAlchemy 2.0 async ORM.

Tables:
  cases         — one row per credit appraisal case
  documents     — uploaded files linked to a case
  recon_flags   — reconciliation flags raised during ingestion
  research_results — cached external research output
  scoring_results  — Five Cs scorecard + recommendation
  audit_logs    — append-only immutable log of every action

Design: All writes go through helper functions that also append to audit_logs.
No UPDATE or DELETE is ever issued to audit_logs.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, Boolean, JSON, ForeignKey, Index
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship

from config import settings


# ── Engine & Session Factory ───────────────────────────────────────────────────

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Base ORM Class ─────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── ORM Models ────────────────────────────────────────────────────────────────

class Case(Base):
    """
    Central record for a credit appraisal case.
    status: draft | ingesting | researching | scoring | cam_ready | complete | rejected
    """
    __tablename__ = "cases"

    id              = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_name    = Column(String(255), nullable=False, index=True)
    company_cin     = Column(String(21),  nullable=True,  index=True)
    company_pan     = Column(String(10),  nullable=True)
    requested_amount_cr = Column(Float,   nullable=True)   # ₹ Crore
    requested_tenor_yr  = Column(Integer, nullable=True)
    purpose         = Column(Text,        nullable=True)
    status          = Column(String(30),  nullable=False, default="draft")
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                             onupdate=lambda: datetime.now(timezone.utc))
    created_by      = Column(String(100), nullable=True, default="system")

    # Relationships
    documents        = relationship("Document",       back_populates="case", cascade="all, delete-orphan")
    recon_flags      = relationship("ReconFlag",      back_populates="case", cascade="all, delete-orphan")
    research_results = relationship("ResearchResult", back_populates="case", cascade="all, delete-orphan")
    scoring_results  = relationship("ScoringResult",  back_populates="case", cascade="all, delete-orphan")
    audit_logs       = relationship("AuditLog",       back_populates="case")


class Document(Base):
    """
    Uploaded document linked to a case.
    doc_type: annual_report | balance_sheet | gstr_2a | gstr_3b | bank_statement |
              itr | sanction_letter | legal_notice | board_minutes | other
    """
    __tablename__ = "documents"

    id              = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id         = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    filename        = Column(String(500), nullable=False)
    doc_type        = Column(String(50),  nullable=False, default="other")
    file_path       = Column(String(1000), nullable=False)
    file_size_bytes = Column(Integer,      nullable=True)
    file_hash       = Column(String(64),   nullable=True)   # SHA-256 of raw file
    mime_type       = Column(String(100),  nullable=True)
    status          = Column(String(30),   nullable=False, default="uploaded")
    # status: uploaded | processing | extracted | failed | flagged
    ocr_confidence_avg  = Column(Float,  nullable=True)    # Average Tesseract confidence
    extracted_json      = Column(JSON,   nullable=True)    # Normalized extracted fields
    extraction_warnings = Column(JSON,   nullable=True)    # List of warning strings
    page_count          = Column(Integer, nullable=True)
    uploaded_at    = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at   = Column(DateTime, nullable=True)

    case = relationship("Case", back_populates="documents")

    __table_args__ = (Index("ix_documents_case_type", "case_id", "doc_type"),)


class ReconFlag(Base):
    """
    Reconciliation / anomaly flags raised by the ingestor.
    severity: CRITICAL | HIGH | MEDIUM | LOW | INFO
    flag_type: CIRCULAR_TRADING | ITC_OVERCLAIM | REVENUE_INFLATION |
               SUPPLIER_NONCOMPLIANCE | DEBTOR_DAYS_HIGH | RELATED_PARTY_HIGH |
               WORKING_CAPITAL_STRESS | CAGR_ANOMALY
    """
    __tablename__ = "recon_flags"

    id          = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id     = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    flag_type   = Column(String(80),  nullable=False, index=True)
    severity    = Column(String(20),  nullable=False)       # CRITICAL / HIGH / MEDIUM / LOW
    title       = Column(String(255), nullable=False)
    description = Column(Text,        nullable=False)
    metric_name  = Column(String(100), nullable=True)       # e.g. "ITC_delta_pct"
    metric_value = Column(Float,       nullable=True)
    threshold    = Column(Float,       nullable=True)
    source_doc_ids = Column(JSON,      nullable=True)       # list of document ids
    detected_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    case = relationship("Case", back_populates="recon_flags")


class ResearchResult(Base):
    """
    Output from the Research Agent for a given case.
    result_type: news_article | mca_filing | ecourts_case | bse_disclosure | rbi_circular
    """
    __tablename__ = "research_results"

    id          = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id     = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    result_type = Column(String(50),  nullable=False, index=True)
    title       = Column(Text,        nullable=True)
    url         = Column(Text,        nullable=True)
    source_name = Column(String(100), nullable=True)
    published_date = Column(DateTime, nullable=True)
    raw_text    = Column(Text,        nullable=True)
    risk_tier   = Column(Integer,     nullable=True)    # 1=Critical, 2=High, 3=Monitor, None=Neutral
    risk_score_delta = Column(Integer, nullable=True)   # Negative = risk deduction
    matched_keywords = Column(JSON,   nullable=True)    # List of matched phrases
    is_cached    = Column(Boolean, default=False)
    retrieved_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    case = relationship("Case", back_populates="research_results")


class ScoringResult(Base):
    """
    Five Cs scorecard output. One row per scoring run per case.
    Immutable — never updated; new rows added on re-score.
    """
    __tablename__ = "scoring_results"

    id              = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id         = Column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    version         = Column(Integer,    nullable=False, default=1)   # Increments on re-score

    # Feature values (raw inputs to scorer)
    feature_values  = Column(JSON, nullable=False)    # {feature_name: raw_value}

    # Score contributions
    score_contributions = Column(JSON, nullable=False)
    # {feature_name: {raw_value, points_earned, max_points, pct_of_max, c_bucket}}

    # Five Cs sub-scores
    character_score  = Column(Float, nullable=False)
    capacity_score   = Column(Float, nullable=False)
    capital_score    = Column(Float, nullable=False)
    collateral_score = Column(Float, nullable=False)
    conditions_score = Column(Float, nullable=False)

    # Final output
    total_raw_score    = Column(Float, nullable=False)    # 0-200
    normalized_score   = Column(Float, nullable=False)    # 0-100
    risk_grade         = Column(String(5), nullable=False)  # A+/A/B+/B/C/D
    decision           = Column(String(20), nullable=False)  # APPROVE/PARTIAL/REJECT

    # Loan recommendation
    recommended_amount_cr   = Column(Float, nullable=True)
    recommended_rate_pct    = Column(Float, nullable=True)
    recommended_tenor_yr    = Column(Integer, nullable=True)
    loan_limit_dscr_cr      = Column(Float, nullable=True)
    loan_limit_collateral_cr = Column(Float, nullable=True)
    loan_limit_drawing_power_cr = Column(Float, nullable=True)

    # Rejection / condition reasoning
    primary_rejection_trigger = Column(Text, nullable=True)
    secondary_factors         = Column(JSON, nullable=True)  # list of strings
    counter_factual           = Column(Text, nullable=True)
    conditions_list           = Column(JSON, nullable=True)  # list of approval conditions

    # Analyst override metadata
    is_overridden      = Column(Boolean, default=False)
    override_by        = Column(String(100), nullable=True)
    override_reason    = Column(Text, nullable=True)
    override_delta     = Column(Float, nullable=True)

    # ML validator output (optional)
    xgb_prediction     = Column(String(20), nullable=True)   # "APPROVE"/"REJECT"
    xgb_probability    = Column(Float, nullable=True)
    ml_agrees_with_scorecard = Column(Boolean, nullable=True)

    scored_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    scored_by  = Column(String(100), nullable=True, default="system")

    case = relationship("Case", back_populates="scoring_results")


class AuditLog(Base):
    """
    Immutable append-only audit log.
    Every significant action is recorded here.
    action_type: CASE_CREATED | DOCUMENT_UPLOADED | EXTRACTION_COMPLETE |
                 RECON_FLAG_RAISED | RESEARCH_TRIGGERED | RESEARCH_COMPLETE |
                 SCORE_COMPUTED | ANALYST_OVERRIDE | CAM_GENERATED | DOWNLOAD
    """
    __tablename__ = "audit_logs"

    id          = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    case_id     = Column(String(36), ForeignKey("cases.id"), nullable=True, index=True)
    session_id  = Column(String(36), nullable=True)
    actor       = Column(String(100), nullable=False, default="system")
    action_type = Column(String(60),  nullable=False, index=True)
    description = Column(Text,        nullable=True)
    input_hash  = Column(String(64),  nullable=True)   # SHA-256 of serialised input
    output_hash = Column(String(64),  nullable=True)   # SHA-256 of serialised output
    extra_metadata = Column(JSON,     nullable=True)    # Extra context (model version, etc.)
    timestamp   = Column(DateTime,    nullable=False,
                         default=lambda: datetime.now(timezone.utc), index=True)

    case = relationship("Case", back_populates="audit_logs")


# ── Database Lifecycle ─────────────────────────────────────────────────────────

async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """FastAPI dependency: yield an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── CRUD Helpers ───────────────────────────────────────────────────────────────

def _sha256(data: Any) -> str:
    """Compute SHA-256 hex digest of any JSON-serialisable object."""
    raw = json.dumps(data, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


async def log_action(
    session: AsyncSession,
    action_type: str,
    description: str,
    case_id: str | None = None,
    actor: str = "system",
    input_data: Any = None,
    output_data: Any = None,
    extra_metadata: dict | None = None,
) -> AuditLog:
    """
    Append an immutable audit record.
    This function is called by every module after every significant operation.
    """
    entry = AuditLog(
        case_id=case_id,
        actor=actor,
        action_type=action_type,
        description=description,
        input_hash=_sha256(input_data) if input_data is not None else None,
        output_hash=_sha256(output_data) if output_data is not None else None,
        extra_metadata=extra_metadata or {},
    )
    session.add(entry)
    await session.flush()   # Get the ID without committing (caller commits)
    return entry


async def create_case(
    session: AsyncSession,
    company_name: str,
    company_cin: str | None = None,
    company_pan: str | None = None,
    requested_amount_cr: float | None = None,
    requested_tenor_yr: int | None = None,
    purpose: str | None = None,
    actor: str = "system",
) -> Case:
    case = Case(
        company_name=company_name,
        company_cin=company_cin,
        company_pan=company_pan,
        requested_amount_cr=requested_amount_cr,
        requested_tenor_yr=requested_tenor_yr,
        purpose=purpose,
        created_by=actor,
    )
    session.add(case)
    await session.flush()
    await log_action(
        session, "CASE_CREATED",
        f"New credit case created for {company_name}",
        case_id=case.id,
        actor=actor,
        output_data={"case_id": case.id, "company": company_name},
    )
    return case


async def add_document(
    session: AsyncSession,
    case_id: str,
    filename: str,
    doc_type: str,
    file_path: str,
    file_size_bytes: int,
    file_hash: str,
    mime_type: str,
    actor: str = "system",
) -> Document:
    doc = Document(
        case_id=case_id,
        filename=filename,
        doc_type=doc_type,
        file_path=file_path,
        file_size_bytes=file_size_bytes,
        file_hash=file_hash,
        mime_type=mime_type,
    )
    session.add(doc)
    await session.flush()
    await log_action(
        session, "DOCUMENT_UPLOADED",
        f"Document uploaded: {filename} ({doc_type})",
        case_id=case_id,
        actor=actor,
        input_data={"filename": filename, "doc_type": doc_type, "hash": file_hash},
        output_data={"doc_id": doc.id},
    )
    return doc


async def add_recon_flag(
    session: AsyncSession,
    case_id: str,
    flag_type: str,
    severity: str,
    title: str,
    description: str,
    metric_name: str | None = None,
    metric_value: float | None = None,
    threshold: float | None = None,
    source_doc_ids: list[str] | None = None,
) -> ReconFlag:
    flag = ReconFlag(
        case_id=case_id,
        flag_type=flag_type,
        severity=severity,
        title=title,
        description=description,
        metric_name=metric_name,
        metric_value=metric_value,
        threshold=threshold,
        source_doc_ids=source_doc_ids or [],
    )
    session.add(flag)
    await session.flush()
    await log_action(
        session, "RECON_FLAG_RAISED",
        f"[{severity}] {flag_type}: {title}",
        case_id=case_id,
        extra_metadata={"flag_id": flag.id, "metric_value": metric_value},
    )
    return flag