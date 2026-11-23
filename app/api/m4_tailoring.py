from datetime import date as date_type

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import AnyAuth, StrategyAccess, WriteAccess
from ..errors import AppError
from ..models import (
    PilotProgram,
    ROICalculation,
    ROICaseStudy,
    SectorSolution,
    Stakeholder,
)
from ..repositories import GenericRepository
from ..services.shared import PilotLifecycleService, ResponsibleAiService, RoiCalculatorService

router = APIRouter(tags=["module4-solution-tailoring"])

SECTORS = ("sante", "finance", "transport", "manufacture")


class SolutionCreate(BaseModel):
    sector: str = Field(pattern="^(sante|finance|transport|manufacture)$")
    use_cases: list[str] = Field(default_factory=list)
    differentiators: list[str] = Field(default_factory=list)
    privacy_impact_level: str = Field(default="unknown", pattern="^(low|medium|high|unknown)$")
    privacy_measures: list[str] = Field(default_factory=list)
    fairness_status: str = Field(default="missing", pattern="^(missing|in_progress|done)$")


class SolutionUpdate(BaseModel):
    sector: str | None = None
    use_cases: list[str] | None = None
    differentiators: list[str] | None = None
    privacy_impact_level: str | None = None
    privacy_measures: list[str] | None = None
    fairness_status: str | None = None


class EthicsReview(BaseModel):
    status: str = Field(pattern="^(pending|in_review|validated|rejected)$")
    date: date_type | None = None


class SolutionResponse(BaseModel):
    id: int
    sector: str
    use_cases: list
    differentiators: list
    status: str
    ethics_status: str
    ethics_review_date: date_type | None
    privacy_impact_level: str
    privacy_measures: list
    fairness_status: str

    model_config = {"from_attributes": True}


class ROICaseCreate(BaseModel):
    sector: str = Field(pattern="^(sante|finance|transport|manufacture)$")
    assumptions: dict = Field(default_factory=dict)
    gains: dict = Field(default_factory=dict)
    horizon_months: int = Field(default=36, ge=1, le=240)


class ROICaseResponse(BaseModel):
    id: int
    sector: str
    assumptions: dict
    gains: dict
    horizon_months: int

    model_config = {"from_attributes": True}


class ROIInput(BaseModel):
    initial_cost: float = Field(ge=0)
    annual_cost: float = Field(default=0, ge=0)
    annual_gain: float = Field(ge=0)
    horizon_months: int = Field(ge=1, le=240)
    case_study_id: int | None = None


class ROIResult(BaseModel):
    roi_percent: float
    payback_months: float | None
    risk_level: str
    risk_indicators: list[str]
    total_cost: float
    total_gain: float


class PilotCreate(BaseModel):
    stakeholder_id: int
    solution_id: int
    scope: str = ""
    milestones: list = Field(default_factory=list)
    ethics_review_status: str = Field(pattern="^(pending|in_review|validated|rejected)$")
    ethics_review_date: date_type | None = None
    privacy_impact_level: str = Field(pattern="^(low|medium|high|unknown)$")
    privacy_measures: list[str] = Field(default_factory=list)
    fairness_status: str = Field(pattern="^(missing|in_progress|done)$")


class PilotUpdate(BaseModel):
    scope: str | None = None
    milestones: list | None = None
    measured_results: dict | None = None
    ethics_review_status: str | None = None
    ethics_review_date: date_type | None = None
    privacy_impact_level: str | None = None
    privacy_measures: list[str] | None = None
    fairness_status: str | None = None


class TransitionRequest(BaseModel):
    to: str = Field(pattern="^(planned|running|completed|failed|cancelled)$")


class PilotResponse(BaseModel):
    id: int
    stakeholder_id: int
    solution_id: int
    scope: str
    milestones: list
    measured_results: dict
    status: str
    ethics_review_status: str
    ethics_review_date: date_type | None
    privacy_impact_level: str
    privacy_measures: list
    fairness_status: str

    model_config = {"from_attributes": True}


def _get_solution(db: Session, id: int) -> SectorSolution:
    obj = db.get(SectorSolution, id)
    if obj is None:
        raise AppError("error.solution_not_found", status_code=404, id=id, resource="sector_solution")
    return obj


def _get_pilot(db: Session, id: int) -> PilotProgram:
    obj = db.get(PilotProgram, id)
    if obj is None:
        raise AppError("error.pilot_not_found", status_code=404, id=id, resource="pilot")
    return obj


@router.post("/sector-solutions", response_model=SolutionResponse, status_code=201)
def create_solution(payload: SolutionCreate, db: Session = Depends(get_db), user=WriteAccess):
    return GenericRepository(db, SectorSolution).add(SectorSolution(**payload.model_dump()))


@router.get("/sector-solutions", response_model=list[SolutionResponse])
def list_solutions(sector: str | None = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    stmt = select(SectorSolution)
    if sector:
        stmt = stmt.where(SectorSolution.sector == sector)
    return GenericRepository(db, SectorSolution).list(skip, limit, stmt)


@router.get("/sector-solutions/{id}", response_model=SolutionResponse)
def get_solution(id: int, db: Session = Depends(get_db), user=AnyAuth):
    return _get_solution(db, id)


@router.patch("/sector-solutions/{id}", response_model=SolutionResponse)
def update_solution(id: int, payload: SolutionUpdate, db: Session = Depends(get_db), user=WriteAccess):
    obj = _get_solution(db, id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.flush()
    db.refresh(obj)
    return obj


@router.delete("/sector-solutions/{id}", status_code=204)
def delete_solution(id: int, db: Session = Depends(get_db), user=StrategyAccess):
    GenericRepository(db, SectorSolution).delete(_get_solution(db, id))


@router.post("/sector-solutions/{id}/ethics-review", response_model=SolutionResponse)
def set_ethics_review(id: int, payload: EthicsReview, db: Session = Depends(get_db), user=StrategyAccess):
    obj = _get_solution(db, id)
    obj.ethics_status = payload.status
    obj.ethics_review_date = payload.date or date_type.today()
    db.flush()
    db.refresh(obj)
    return obj


@router.post("/sector-solutions/{id}/publish", response_model=SolutionResponse)
def publish_solution(id: int, db: Session = Depends(get_db), user=StrategyAccess):
    obj = _get_solution(db, id)
    ResponsibleAiService().assert_publishable(obj)
    obj.status = "published"
    db.flush()
    db.refresh(obj)
    return obj


@router.post("/roi/calculate", response_model=ROIResult)
def calculate_roi(payload: ROIInput, db: Session = Depends(get_db), user=AnyAuth):
    result = RoiCalculatorService().calculate(
        payload.initial_cost, payload.annual_cost, payload.annual_gain, payload.horizon_months
    )
    if payload.case_study_id is not None and db.get(ROICaseStudy, payload.case_study_id) is None:
        raise AppError("error.case_study_not_found", status_code=404, id=payload.case_study_id, resource="roi_case_study")
    rec = ROICalculation(
        case_study_id=payload.case_study_id,
        inputs=payload.model_dump(),
        roi_percent=result["roi_percent"],
        payback_months=result["payback_months"],
        risk_level=result["risk_level"],
        risk_indicators=result["risk_indicators"],
    )
    db.add(rec)
    db.flush()
    return ROIResult(**result)


@router.post("/roi-case-studies", response_model=ROICaseResponse, status_code=201)
def create_roi_case(payload: ROICaseCreate, db: Session = Depends(get_db), user=WriteAccess):
    return GenericRepository(db, ROICaseStudy).add(ROICaseStudy(**payload.model_dump()))


@router.get("/roi-case-studies", response_model=list[ROICaseResponse])
def list_roi_cases(sector: str | None = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    stmt = select(ROICaseStudy)
    if sector:
        stmt = stmt.where(ROICaseStudy.sector == sector)
    return GenericRepository(db, ROICaseStudy).list(skip, limit, stmt)


@router.get("/roi-case-studies/{id}", response_model=ROICaseResponse)
def get_roi_case(id: int, db: Session = Depends(get_db), user=AnyAuth):
    return GenericRepository(db, ROICaseStudy).get(id)


@router.post("/pilots", response_model=PilotResponse, status_code=201)
def create_pilot(payload: PilotCreate, db: Session = Depends(get_db), user=WriteAccess):
    if db.get(Stakeholder, payload.stakeholder_id) is None:
        raise AppError("error.stakeholder_not_found", status_code=404, id=payload.stakeholder_id, resource="stakeholder")
    _get_solution(db, payload.solution_id)
    return GenericRepository(db, PilotProgram).add(PilotProgram(**payload.model_dump()))


@router.get("/pilots", response_model=list[PilotResponse])
def list_pilots(status: str | None = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    stmt = select(PilotProgram)
    if status:
        stmt = stmt.where(PilotProgram.status == status)
    return GenericRepository(db, PilotProgram).list(skip, limit, stmt)


@router.get("/pilots/{id}", response_model=PilotResponse)
def get_pilot(id: int, db: Session = Depends(get_db), user=AnyAuth):
    return _get_pilot(db, id)


@router.patch("/pilots/{id}", response_model=PilotResponse)
def update_pilot(id: int, payload: PilotUpdate, db: Session = Depends(get_db), user=WriteAccess):
    obj = _get_pilot(db, id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.flush()
    db.refresh(obj)
    return obj


@router.post("/pilots/{id}/transition", response_model=PilotResponse)
def transition_pilot(id: int, payload: TransitionRequest, db: Session = Depends(get_db), user=WriteAccess):
    obj = _get_pilot(db, id)
    PilotLifecycleService().transition(obj, payload.to)
    db.flush()
    db.refresh(obj)
    return obj


@router.get("/recommendations/content")
def recommend_content(
    persona_id: int | None = None,
    sector: str | None = None,
    db: Session = Depends(get_db),
    user=AnyAuth,
):
    stmt = select(ROICaseStudy)
    if sector:
        stmt = stmt.where(ROICaseStudy.sector == sector)
    cases = list(db.execute(stmt).scalars())
    pilot_stmt = select(PilotProgram)
    if sector:
        pilot_stmt = pilot_stmt.join(SectorSolution, PilotProgram.solution_id == SectorSolution.id).where(
            SectorSolution.sector == sector
        )
    pilots = list(db.execute(pilot_stmt).scalars())
    preferences = []
    if persona_id is not None:
        from ..models import Persona

        persona = db.get(Persona, persona_id)
        if persona is not None:
            preferences = persona.solution_preferences
    return {
        "sector": sector,
        "persona_id": persona_id,
        "solution_preferences": preferences,
        "roi_case_studies": [ROICaseResponse.model_validate(c) for c in cases],
        "pilots": [PilotResponse.model_validate(p) for p in pilots],
    }
