from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import AnyAuth, StrategyAccess, WriteAccess
from ..errors import AppError
from ..models import BudgetLine, Contingency, ContingencyDraw, ResourceAllocation
from ..repositories import GenericRepository
from ..services.shared import BudgetGuardService

router = APIRouter(tags=["module9-finance-resources"])


class BudgetLineCreate(BaseModel):
    pillar: int = Field(ge=1, le=8)
    allocated: float = Field(ge=0)
    consumed: float = Field(default=0, ge=0)
    fiscal_year: int = Field(ge=2000, le=2100)


class BudgetLineResponse(BaseModel):
    id: int
    pillar: int
    allocated: float
    consumed: float
    fiscal_year: int

    model_config = {"from_attributes": True}


class ConsumeRequest(BaseModel):
    amount: float = Field(gt=0)
    justification: str = ""


class ResourceAllocationCreate(BaseModel):
    budget_line_id: int
    type: str = Field(pattern="^(equipe_vente|campagne|evenement|outil_intelligence)$")
    cost: float = Field(ge=0)
    attachment: str = ""


class ResourceAllocationResponse(BaseModel):
    id: int
    budget_line_id: int
    type: str
    cost: float
    attachment: str

    model_config = {"from_attributes": True}


class ContingencyCreate(BaseModel):
    risk_scenario: str = Field(min_length=1, max_length=255)
    provision: float = Field(gt=0)
    trigger_conditions: list[str] = Field(default_factory=list)


class ContingencyResponse(BaseModel):
    id: int
    risk_scenario: str
    provision: float
    trigger_conditions: list
    drawn: float

    model_config = {"from_attributes": True}


class DrawRequest(BaseModel):
    budget_line_id: int
    amount: float = Field(gt=0)
    justification: str = ""


def _get_line(db: Session, id: int) -> BudgetLine:
    obj = db.get(BudgetLine, id)
    if obj is None:
        raise AppError("error.budget_line_not_found", status_code=404, id=id, resource="budget_line")
    return obj


def _get_contingency(db: Session, id: int) -> Contingency:
    obj = db.get(Contingency, id)
    if obj is None:
        raise AppError("error.contingency_not_found", status_code=404, id=id, resource="contingency")
    return obj


@router.post("/budget-lines", response_model=BudgetLineResponse, status_code=201)
def create_budget_line(payload: BudgetLineCreate, db: Session = Depends(get_db), user=StrategyAccess):
    return GenericRepository(db, BudgetLine).add(BudgetLine(**payload.model_dump()))


@router.get("/budget-lines", response_model=list[BudgetLineResponse])
def list_budget_lines(fiscal_year: int | None = None, pillar: int | None = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    stmt = select(BudgetLine)
    if fiscal_year is not None:
        stmt = stmt.where(BudgetLine.fiscal_year == fiscal_year)
    if pillar is not None:
        stmt = stmt.where(BudgetLine.pillar == pillar)
    return GenericRepository(db, BudgetLine).list(skip, limit, stmt)


@router.get("/budget-lines/{id}", response_model=BudgetLineResponse)
def get_budget_line(id: int, db: Session = Depends(get_db), user=AnyAuth):
    return _get_line(db, id)


@router.post("/budget-lines/{id}/consume")
def consume(id: int, payload: ConsumeRequest, db: Session = Depends(get_db), user=WriteAccess):
    line = _get_line(db, id)
    return BudgetGuardService().consume(db, line, payload.amount, payload.justification)


@router.get("/budget/report")
def budget_report(fiscal_year: int | None = None, db: Session = Depends(get_db), user=AnyAuth):
    return {"fiscal_year": fiscal_year, "lines": BudgetGuardService().report(db, fiscal_year)}


@router.post("/resource-allocations", response_model=ResourceAllocationResponse, status_code=201)
def create_allocation(payload: ResourceAllocationCreate, db: Session = Depends(get_db), user=StrategyAccess):
    _get_line(db, payload.budget_line_id)
    return GenericRepository(db, ResourceAllocation).add(ResourceAllocation(**payload.model_dump()))


@router.get("/resource-allocations", response_model=list[ResourceAllocationResponse])
def list_allocations(budget_line_id: int | None = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    stmt = select(ResourceAllocation)
    if budget_line_id is not None:
        stmt = stmt.where(ResourceAllocation.budget_line_id == budget_line_id)
    return GenericRepository(db, ResourceAllocation).list(skip, limit, stmt)


@router.post("/contingencies", response_model=ContingencyResponse, status_code=201)
def create_contingency(payload: ContingencyCreate, db: Session = Depends(get_db), user=StrategyAccess):
    contingency = Contingency(
        risk_scenario=payload.risk_scenario,
        provision=payload.provision,
        trigger_conditions=payload.trigger_conditions,
    )
    BudgetGuardService().add_contingency(db, contingency)
    return GenericRepository(db, Contingency).add(contingency)


@router.get("/contingencies", response_model=list[ContingencyResponse])
def list_contingencies(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    return GenericRepository(db, Contingency).list(skip, limit)


@router.get("/contingencies/{id}", response_model=ContingencyResponse)
def get_contingency(id: int, db: Session = Depends(get_db), user=AnyAuth):
    return _get_contingency(db, id)


@router.post("/contingencies/{id}/draw")
def draw_contingency(id: int, payload: DrawRequest, db: Session = Depends(get_db), user=StrategyAccess):
    contingency = _get_contingency(db, id)
    line = _get_line(db, payload.budget_line_id)
    guard = BudgetGuardService()
    reserve = guard.reserve(db)
    if payload.amount > reserve["remaining"] or payload.amount > contingency.provision - contingency.drawn:
        from ..errors import AppError as _AE

        raise _AE("error.budget_exceeded", status_code=409, overage=payload.amount)
    contingency.drawn = round(contingency.drawn + payload.amount, 2)
    draw = ContingencyDraw(
        budget_line_id=line.id, contingency_id=contingency.id, amount=payload.amount, justification=payload.justification
    )
    db.add(draw)
    db.flush()
    return {"contingency_id": contingency.id, "drawn": contingency.drawn, "draw_id": draw.id, "reserve": guard.reserve(db)}


@router.get("/contingency/reserve")
def contingency_reserve(db: Session = Depends(get_db), user=AnyAuth):
    return BudgetGuardService().reserve(db)
