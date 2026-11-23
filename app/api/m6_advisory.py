from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import AnyAuth, StrategyAccess, WriteAccess
from ..errors import AppError
from ..models import AdvisoryBoard, AdvisoryInsight, Advisor, BoardMembership
from ..repositories import GenericRepository
from ..services.shared import StrategyAdjustmentService

router = APIRouter(tags=["module6-advisory-boards"])


class BoardCreate(BaseModel):
    theme: str = Field(min_length=1, max_length=255)
    scope: str = Field(min_length=1, max_length=120)


class BoardResponse(BaseModel):
    id: int
    theme: str
    scope: str

    model_config = {"from_attributes": True}


class AdvisorCreate(BaseModel):
    profile: str = Field(min_length=1, max_length=255)
    expertise: list[str] = Field(default_factory=list)
    networks: list[str] = Field(default_factory=list)
    engagement: str = Field(default="active")
    notability: int = Field(default=3, ge=1, le=5)


class AdvisorResponse(BaseModel):
    id: int
    profile: str
    expertise: list
    networks: list
    engagement: str
    notability: int

    model_config = {"from_attributes": True}


class InsightCreate(BaseModel):
    advisor_id: int
    board_id: int
    recommendation: str = Field(min_length=1)
    domain: str = Field(min_length=1, max_length=120)


class InsightResponse(BaseModel):
    id: int
    advisor_id: int
    board_id: int
    recommendation: str
    domain: str
    status: str

    model_config = {"from_attributes": True}


class ApplyRequest(BaseModel):
    decision: str = Field(min_length=1)


def _get(db, model, id, code):
    obj = db.get(model, id)
    if obj is None:
        raise AppError(code, status_code=404, id=id, resource=model.__tablename__)
    return obj


@router.post("/advisory-boards", response_model=BoardResponse, status_code=201)
def create_board(payload: BoardCreate, db: Session = Depends(get_db), user=WriteAccess):
    return GenericRepository(db, AdvisoryBoard).add(AdvisoryBoard(**payload.model_dump()))


@router.get("/advisory-boards", response_model=list[BoardResponse])
def list_boards(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    return GenericRepository(db, AdvisoryBoard).list(skip, limit)


@router.get("/advisory-boards/{id}", response_model=BoardResponse)
def get_board(id: int, db: Session = Depends(get_db), user=AnyAuth):
    return _get(db, AdvisoryBoard, id, "error.board_not_found")


@router.post("/advisors", response_model=AdvisorResponse, status_code=201)
def create_advisor(payload: AdvisorCreate, db: Session = Depends(get_db), user=WriteAccess):
    return GenericRepository(db, Advisor).add(Advisor(**payload.model_dump()))


@router.get("/advisors", response_model=list[AdvisorResponse])
def list_advisors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    return GenericRepository(db, Advisor).list(skip, limit)


@router.get("/advisors/{id}", response_model=AdvisorResponse)
def get_advisor(id: int, db: Session = Depends(get_db), user=AnyAuth):
    return _get(db, Advisor, id, "error.advisor_not_found")


@router.put("/advisory-boards/{board_id}/members/{advisor_id}")
def add_member(board_id: int, advisor_id: int, db: Session = Depends(get_db), user=WriteAccess):
    _get(db, AdvisoryBoard, board_id, "error.board_not_found")
    _get(db, Advisor, advisor_id, "error.advisor_not_found")
    if db.get(BoardMembership, (board_id, advisor_id)) is None:
        db.add(BoardMembership(board_id=board_id, advisor_id=advisor_id))
        db.flush()
    return {"board_id": board_id, "advisor_id": advisor_id}


@router.post("/advisory-insights", response_model=InsightResponse, status_code=201)
def create_insight(payload: InsightCreate, db: Session = Depends(get_db), user=WriteAccess):
    _get(db, Advisor, payload.advisor_id, "error.advisor_not_found")
    _get(db, AdvisoryBoard, payload.board_id, "error.board_not_found")
    return GenericRepository(db, AdvisoryInsight).add(AdvisoryInsight(**payload.model_dump()))


@router.get("/advisory-insights", response_model=list[InsightResponse])
def list_insights(status: str | None = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    stmt = select(AdvisoryInsight)
    if status:
        stmt = stmt.where(AdvisoryInsight.status == status)
    return GenericRepository(db, AdvisoryInsight).list(skip, limit, stmt)


@router.get("/advisory-insights/{id}", response_model=InsightResponse)
def get_insight(id: int, db: Session = Depends(get_db), user=AnyAuth):
    return _get(db, AdvisoryInsight, id, "error.insight_not_found")


@router.post("/advisory-insights/{id}/apply")
def apply_insight(id: int, payload: ApplyRequest, db: Session = Depends(get_db), user=StrategyAccess):
    insight = _get(db, AdvisoryInsight, id, "error.insight_not_found")
    adj = StrategyAdjustmentService().create(
        db,
        trigger_type="advisory_insight",
        decision=payload.decision,
        advisory_insight_id=insight.id,
        detail=f"insight:{insight.id}",
    )
    insight.status = "applied"
    db.flush()
    return {"insight_id": insight.id, "status": insight.status, "adjustment_id": adj.id}


@router.get("/advisory/credibility-dashboard")
def credibility_dashboard(db: Session = Depends(get_db), user=AnyAuth):
    advisors = list(db.execute(select(Advisor)).scalars())
    insights = list(db.execute(select(AdvisoryInsight)).scalars())
    boards = list(db.execute(select(AdvisoryBoard)).scalars())
    memberships = list(db.execute(select(BoardMembership)).scalars())
    applied = [i for i in insights if i.status == "applied"]
    return {
        "boards": len(boards),
        "advisors": len(advisors),
        "memberships": len(memberships),
        "average_notability": round(sum(a.notability for a in advisors) / len(advisors), 2) if advisors else 0.0,
        "insights_total": len(insights),
        "insights_applied": len(applied),
        "credibility_index": round(
            100
            * (
                0.4 * min(1.0, len(advisors) / 10.0)
                + 0.3 * ((sum(a.notability for a in advisors) / len(advisors) / 5.0) if advisors else 0.0)
                + 0.3 * min(1.0, len(applied) / 5.0)
            ),
            2,
        ),
    }
