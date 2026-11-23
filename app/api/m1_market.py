from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import AnyAuth, StrategyAccess, WriteAccess
from ..errors import AppError
from ..models import CaseStudy, Competitor, MarketSignal, SignalAlert
from ..repositories import GenericRepository
from ..services.shared import SignalScoringService

router = APIRouter(tags=["module1-market-insight"])


# ---- Competitors ----

class CompetitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    sector: str = Field(min_length=1, max_length=120)
    market_share: float = Field(default=0.0, ge=0.0, le=1.0)
    offers: list[str] = Field(default_factory=list)
    segments: list[str] = Field(default_factory=list)
    initiatives: list[str] = Field(default_factory=list)


class CompetitorUpdate(BaseModel):
    name: str | None = None
    sector: str | None = None
    market_share: float | None = Field(default=None, ge=0.0, le=1.0)
    offers: list[str] | None = None
    segments: list[str] | None = None
    initiatives: list[str] | None = None


class CompetitorResponse(BaseModel):
    id: int
    name: str
    sector: str
    market_share: float
    offers: list
    segments: list
    initiatives: list

    model_config = {"from_attributes": True}


def _comp_repo(db: Session) -> GenericRepository[Competitor]:
    return GenericRepository(db, Competitor)


def _get_competitor(db: Session, id: int) -> Competitor:
    obj = _comp_repo(db).get(id)
    if obj is None:
        raise AppError("error.competitor_not_found", status_code=404, id=id, resource="competitor")
    return obj


@router.post("/competitors", response_model=CompetitorResponse, status_code=201)
def create_competitor(payload: CompetitorCreate, db: Session = Depends(get_db), user=WriteAccess):
    if db.execute(select(Competitor).where(Competitor.name == payload.name)).first():
        raise AppError("error.duplicate", status_code=409, field=payload.name)
    return _comp_repo(db).add(Competitor(**payload.model_dump()))


@router.get("/competitors", response_model=list[CompetitorResponse])
def list_competitors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    return _comp_repo(db).list(skip, limit)


@router.get("/competitors/{id}", response_model=CompetitorResponse)
def get_competitor(id: int, db: Session = Depends(get_db), user=AnyAuth):
    return _get_competitor(db, id)


@router.patch("/competitors/{id}", response_model=CompetitorResponse)
def update_competitor(id: int, payload: CompetitorUpdate, db: Session = Depends(get_db), user=WriteAccess):
    obj = _get_competitor(db, id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.flush()
    db.refresh(obj)
    return obj


@router.delete("/competitors/{id}", status_code=204)
def delete_competitor(id: int, db: Session = Depends(get_db), user=StrategyAccess):
    _comp_repo(db).delete(_get_competitor(db, id))


# ---- Signals ----

class SignalCreate(BaseModel):
    competitor_id: int
    type: str = Field(pattern="^(lancement|partenariat|campagne|investissement)$")
    source: str = Field(min_length=1, max_length=255)
    date: date


class SignalBatch(BaseModel):
    signals: list[SignalCreate] = Field(min_length=1)


class SignalResponse(BaseModel):
    id: int
    competitor_id: int
    type: str
    source: str
    date: date
    relevance_score: float

    model_config = {"from_attributes": True}


class AlertResponse(BaseModel):
    id: int
    signal_id: int
    threshold: float

    model_config = {"from_attributes": True}


def _ingest(db: Session, payload: SignalCreate) -> MarketSignal:
    if db.get(Competitor, payload.competitor_id) is None:
        raise AppError("error.competitor_not_found", status_code=404, id=payload.competitor_id, resource="competitor")
    signal = MarketSignal(**payload.model_dump())
    db.add(signal)
    db.flush()
    SignalScoringService().evaluate(db, signal)
    db.refresh(signal)
    return signal


@router.post("/signals", response_model=SignalResponse, status_code=201)
def create_signal(payload: SignalCreate, db: Session = Depends(get_db), user=WriteAccess):
    return _ingest(db, payload)


@router.post("/signals/batch", response_model=list[SignalResponse], status_code=201)
def create_signals_batch(payload: SignalBatch, db: Session = Depends(get_db), user=WriteAccess):
    return [_ingest(db, s) for s in payload.signals]


@router.get("/signals", response_model=list[SignalResponse])
def list_signals(
    type: str | None = None,
    competitor_id: int | None = None,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    min_relevance: float | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user=AnyAuth,
):
    stmt = select(MarketSignal)
    if type:
        stmt = stmt.where(MarketSignal.type == type)
    if competitor_id is not None:
        stmt = stmt.where(MarketSignal.competitor_id == competitor_id)
    if from_date:
        stmt = stmt.where(MarketSignal.date >= from_date)
    if to_date:
        stmt = stmt.where(MarketSignal.date <= to_date)
    if min_relevance is not None:
        stmt = stmt.where(MarketSignal.relevance_score >= min_relevance)
    stmt = stmt.order_by(MarketSignal.date.desc())
    return GenericRepository(db, MarketSignal).list(skip, limit, stmt)


@router.get("/signals/alerts", response_model=list[AlertResponse])
def list_alerts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    return GenericRepository(db, SignalAlert).list(skip, limit, select(SignalAlert).order_by(SignalAlert.id.desc()))


class ThresholdUpdate(BaseModel):
    threshold: float = Field(ge=0, le=100)


@router.put("/signals/config/alert-threshold", response_model=ThresholdUpdate)
def set_alert_threshold(payload: ThresholdUpdate, db: Session = Depends(get_db), user=StrategyAccess):
    SignalScoringService().set_threshold(db, payload.threshold)
    return payload


@router.get("/signals/config/alert-threshold", response_model=ThresholdUpdate)
def get_alert_threshold(db: Session = Depends(get_db), user=AnyAuth):
    return ThresholdUpdate(threshold=SignalScoringService().threshold(db))


@router.get("/signals/{id}", response_model=SignalResponse)
def get_signal(id: int, db: Session = Depends(get_db), user=AnyAuth):
    obj = db.get(MarketSignal, id)
    if obj is None:
        raise AppError("error.signal_not_found", status_code=404, id=id, resource="signal")
    return obj


# ---- Case studies ----

class CaseStudyCreate(BaseModel):
    market: str = Field(min_length=1, max_length=255)
    strategy: str = Field(min_length=1)
    results: dict = Field(default_factory=dict)
    lessons: list[str] = Field(default_factory=list)
    reproducible_practices: list[str] = Field(default_factory=list)
    failure_factors: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class CaseStudyResponse(BaseModel):
    id: int
    market: str
    strategy: str
    results: dict
    lessons: list
    reproducible_practices: list
    failure_factors: list
    keywords: list

    model_config = {"from_attributes": True}


@router.post("/case-studies", response_model=CaseStudyResponse, status_code=201)
def create_case_study(payload: CaseStudyCreate, db: Session = Depends(get_db), user=WriteAccess):
    return GenericRepository(db, CaseStudy).add(CaseStudy(**payload.model_dump()))


@router.get("/case-studies", response_model=list[CaseStudyResponse])
def list_case_studies(market: str | None = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    stmt = select(CaseStudy)
    if market:
        stmt = stmt.where(CaseStudy.market == market)
    return GenericRepository(db, CaseStudy).list(skip, limit, stmt)


@router.get("/case-studies/count-by-keyword", response_model=dict[str, int])
def count_by_keyword(db: Session = Depends(get_db), user=AnyAuth):
    counts: dict[str, int] = {}
    for cs in db.execute(select(CaseStudy)).scalars():
        for kw in cs.keywords or []:
            counts[kw] = counts.get(kw, 0) + 1
    return counts


@router.get("/case-studies/{id}", response_model=CaseStudyResponse)
def get_case_study(id: int, db: Session = Depends(get_db), user=AnyAuth):
    obj = db.get(CaseStudy, id)
    if obj is None:
        raise AppError("error.case_study_not_found", status_code=404, id=id, resource="case_study")
    return obj


@router.patch("/case-studies/{id}", response_model=CaseStudyResponse)
def update_case_study(id: int, payload: CaseStudyCreate, db: Session = Depends(get_db), user=WriteAccess):
    obj = db.get(CaseStudy, id)
    if obj is None:
        raise AppError("error.case_study_not_found", status_code=404, id=id, resource="case_study")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    db.flush()
    db.refresh(obj)
    return obj


@router.delete("/case-studies/{id}", status_code=204)
def delete_case_study(id: int, db: Session = Depends(get_db), user=StrategyAccess):
    obj = db.get(CaseStudy, id)
    if obj is None:
        raise AppError("error.case_study_not_found", status_code=404, id=id, resource="case_study")
    GenericRepository(db, CaseStudy).delete(obj)
