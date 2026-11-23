from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import AnyAuth, StrategyAccess, WriteAccess
from ..errors import AppError
from ..models import FeedbackItem, FocusGroup, KpiAlert, KPI, Survey, SurveyResponse
from ..repositories import GenericRepository
from ..services.shared import KpiEvaluationService

router = APIRouter(tags=["module8-feedback-loop"])


class SurveyCreate(BaseModel):
    audience: str = Field(pattern="^(decideurs|clients)$")
    questions: list = Field(default_factory=list)


class SurveyResponseModel(BaseModel):
    id: int
    audience: str
    questions: list

    model_config = {"from_attributes": True}


class AnswerCreate(BaseModel):
    answers: dict = Field(default_factory=dict)


class AnswerResponse(BaseModel):
    id: int
    survey_id: int
    answers: dict
    submitted_at: datetime

    model_config = {"from_attributes": True}


class FocusGroupCreate(BaseModel):
    participants: list = Field(default_factory=list)
    themes: list = Field(default_factory=list)
    synthesis: str = ""


class FocusGroupResponse(BaseModel):
    id: int
    participants: list
    themes: list
    synthesis: str

    model_config = {"from_attributes": True}


class FeedbackCreate(BaseModel):
    source: str = Field(min_length=1, max_length=60)
    verbatim: str = ""
    need: str = ""
    criticality: str = Field(default="medium", pattern="^(low|medium|high)$")


class FeedbackResponse(BaseModel):
    id: int
    source: str
    verbatim: str
    need: str
    criticality: str
    status: str
    linked_adjustment_id: int | None

    model_config = {"from_attributes": True}


class KPICreate(BaseModel):
    type: str = Field(min_length=1, max_length=60)
    value: float
    target: float
    period: str = Field(min_length=1, max_length=20)
    trend: str = Field(default="stable", pattern="^(up|down|stable)$")


class KPIResponse(BaseModel):
    id: int
    type: str
    value: float
    target: float
    period: str
    trend: str

    model_config = {"from_attributes": True}


def _get_survey(db: Session, id: int) -> Survey:
    obj = db.get(Survey, id)
    if obj is None:
        raise AppError("error.survey_not_found", status_code=404, id=id, resource="survey")
    return obj


def _get_kpi(db: Session, id: int) -> KPI:
    obj = db.get(KPI, id)
    if obj is None:
        raise AppError("error.kpi_not_found", status_code=404, id=id, resource="kpi")
    return obj


@router.post("/surveys", response_model=SurveyResponseModel, status_code=201)
def create_survey(payload: SurveyCreate, db: Session = Depends(get_db), user=WriteAccess):
    return GenericRepository(db, Survey).add(Survey(**payload.model_dump()))


@router.get("/surveys", response_model=list[SurveyResponseModel])
def list_surveys(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    return GenericRepository(db, Survey).list(skip, limit)


@router.get("/surveys/{id}", response_model=SurveyResponseModel)
def get_survey(id: int, db: Session = Depends(get_db), user=AnyAuth):
    return _get_survey(db, id)


@router.post("/surveys/{id}/responses", response_model=AnswerResponse, status_code=201)
def add_response(id: int, payload: AnswerCreate, db: Session = Depends(get_db), user=WriteAccess):
    _get_survey(db, id)
    return GenericRepository(db, SurveyResponse).add(SurveyResponse(survey_id=id, answers=payload.answers))


@router.get("/surveys/{id}/responses", response_model=list[AnswerResponse])
def list_responses(id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    _get_survey(db, id)
    stmt = select(SurveyResponse).where(SurveyResponse.survey_id == id)
    return GenericRepository(db, SurveyResponse).list(skip, limit, stmt)


@router.post("/focus-groups", response_model=FocusGroupResponse, status_code=201)
def create_focus_group(payload: FocusGroupCreate, db: Session = Depends(get_db), user=WriteAccess):
    return GenericRepository(db, FocusGroup).add(FocusGroup(**payload.model_dump()))


@router.get("/focus-groups", response_model=list[FocusGroupResponse])
def list_focus_groups(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    return GenericRepository(db, FocusGroup).list(skip, limit)


@router.post("/feedback-items", response_model=FeedbackResponse, status_code=201)
def create_feedback(payload: FeedbackCreate, db: Session = Depends(get_db), user=WriteAccess):
    return GenericRepository(db, FeedbackItem).add(FeedbackItem(**payload.model_dump()))


@router.get("/feedback-items", response_model=list[FeedbackResponse])
def list_feedback(criticality: str | None = None, status: str | None = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    stmt = select(FeedbackItem)
    if criticality:
        stmt = stmt.where(FeedbackItem.criticality == criticality)
    if status:
        stmt = stmt.where(FeedbackItem.status == status)
    return GenericRepository(db, FeedbackItem).list(skip, limit, stmt.order_by(FeedbackItem.id.desc()))


@router.get("/feedback-items/{id}", response_model=FeedbackResponse)
def get_feedback(id: int, db: Session = Depends(get_db), user=AnyAuth):
    obj = db.get(FeedbackItem, id)
    if obj is None:
        raise AppError("error.not_found", status_code=404, resource="feedback_item", id=id)
    return obj


@router.post("/kpis", response_model=KPIResponse, status_code=201)
def create_kpi(payload: KPICreate, db: Session = Depends(get_db), user=WriteAccess):
    return GenericRepository(db, KPI).add(KPI(**payload.model_dump()))


@router.get("/kpis", response_model=list[KPIResponse])
def list_kpis(period: str | None = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    stmt = select(KPI)
    if period:
        stmt = stmt.where(KPI.period == period)
    return GenericRepository(db, KPI).list(skip, limit, stmt)


@router.get("/kpis/dashboard")
def kpi_dashboard(period: str | None = None, db: Session = Depends(get_db), user=AnyAuth):
    svc = KpiEvaluationService()
    stmt = select(KPI)
    if period:
        stmt = stmt.where(KPI.period == period)
    kpis = list(db.execute(stmt).scalars())
    alerts_count = dict(
        (row[0], row[1])
        for row in db.execute(select(KpiAlert.kpi_id, func.count()).group_by(KpiAlert.kpi_id)).all()
    )
    entries = []
    for kpi in kpis:
        dev = svc.deviation(kpi)
        entries.append(
            {
                "kpi_id": kpi.id,
                "type": kpi.type,
                "period": kpi.period,
                "value": kpi.value,
                "target": kpi.target,
                "deviation": None if dev == float("inf") else round(dev, 4),
                "trend": kpi.trend,
                "alert": abs(dev) > svc.threshold(db) if dev != float("inf") else True,
                "alerts_count": alerts_count.get(kpi.id, 0),
            }
        )
    return {"period": period, "threshold": svc.threshold(db), "kpis": entries}


class KpiThreshold(BaseModel):
    threshold: float = Field(ge=0, le=1)


@router.put("/kpis/config/deviation-threshold", response_model=KpiThreshold)
def set_kpi_threshold(payload: KpiThreshold, db: Session = Depends(get_db), user=StrategyAccess):
    KpiEvaluationService().set_threshold(db, payload.threshold)
    return payload


@router.get("/kpis/{id}", response_model=KPIResponse)
def get_kpi(id: int, db: Session = Depends(get_db), user=AnyAuth):
    return _get_kpi(db, id)


@router.post("/kpis/{id}/evaluate")
def evaluate_kpi(id: int, db: Session = Depends(get_db), user=StrategyAccess):
    kpi = _get_kpi(db, id)
    svc = KpiEvaluationService()
    alert = svc.evaluate(db, kpi)
    return {
        "kpi_id": kpi.id,
        "deviation": svc.deviation(kpi),
        "threshold": svc.threshold(db),
        "alert_created": alert is not None,
        "alert_id": alert.id if alert else None,
        "feedback_item_id": alert.feedback_item_id if alert else None,
    }

