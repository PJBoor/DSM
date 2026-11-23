from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import AnyAuth, StrategyAccess, WriteAccess
from ..errors import AppError
from ..models import BenchmarkAxisScore, BenchmarkRun, Collaboration, StrategyAdjustment
from ..repositories import GenericRepository
from ..services.shared import StrategyAdjustmentService

router = APIRouter(tags=["module5-benchmark-alliances"])


class CollaborationCreate(BaseModel):
    type: str = Field(pattern="^(recherche_commune|norme|initiative_sectorielle)$")
    partners: list[str] = Field(default_factory=list)
    theme: str = Field(min_length=1, max_length=255)
    status: str = Field(default="active", pattern="^(active|paused|closed)$")


class CollaborationResponse(BaseModel):
    id: int
    type: str
    partners: list
    theme: str
    status: str

    model_config = {"from_attributes": True}


class AxisInput(BaseModel):
    axis: str = Field(min_length=1, max_length=60)
    our_score: float = Field(ge=0, le=100)
    best_competitor_score: float = Field(ge=0, le=100)


class BenchmarkCreate(BaseModel):
    solution_evaluated: str = Field(min_length=1, max_length=255)
    reference_competitors: list[str] = Field(default_factory=list)
    gap_threshold: float = Field(default=10.0, ge=0, le=100)
    axes: list[AxisInput] = Field(min_length=1)


class AxisResponse(BaseModel):
    id: int
    run_id: int
    axis: str
    our_score: float
    best_competitor_score: float
    gap: float

    model_config = {"from_attributes": True}


class BenchmarkResponse(BaseModel):
    id: int
    solution_evaluated: str
    reference_competitors: list
    differentiation_score: float
    gap_threshold: float
    axes: list[AxisResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AdjustmentCreate(BaseModel):
    trigger_type: str = Field(pattern="^(signal|benchmark|advisory_insight|kpi_gap|manual)$")
    decision: str = Field(min_length=1)
    signal_id: int | None = None
    advisory_insight_id: int | None = None
    feedback_item_id: int | None = None


class AdjustmentResponse(BaseModel):
    id: int
    trigger_type: str
    trigger_detail: str
    signal_id: int | None
    advisory_insight_id: int | None
    feedback_item_id: int | None
    decision: str
    applied_at: str | None

    model_config = {"from_attributes": True}


def _get_run(db: Session, id: int) -> BenchmarkRun:
    obj = db.get(BenchmarkRun, id)
    if obj is None:
        raise AppError("error.benchmark_not_found", status_code=404, id=id, resource="benchmark")
    return obj


def _axes(db: Session, run_id: int) -> list[BenchmarkAxisScore]:
    return list(db.execute(select(BenchmarkAxisScore).where(BenchmarkAxisScore.run_id == run_id)).scalars())


def _run_response(db: Session, run: BenchmarkRun) -> BenchmarkResponse:
    return BenchmarkResponse(
        id=run.id,
        solution_evaluated=run.solution_evaluated,
        reference_competitors=run.reference_competitors,
        differentiation_score=run.differentiation_score,
        gap_threshold=run.gap_threshold,
        axes=[AxisResponse.model_validate(a) for a in _axes(db, run.id)],
    )


@router.post("/collaborations", response_model=CollaborationResponse, status_code=201)
def create_collaboration(payload: CollaborationCreate, db: Session = Depends(get_db), user=WriteAccess):
    return GenericRepository(db, Collaboration).add(Collaboration(**payload.model_dump()))


@router.get("/collaborations", response_model=list[CollaborationResponse])
def list_collaborations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    return GenericRepository(db, Collaboration).list(skip, limit)


@router.get("/collaborations/{id}", response_model=CollaborationResponse)
def get_collaboration(id: int, db: Session = Depends(get_db), user=AnyAuth):
    return GenericRepository(db, Collaboration).get(id)


@router.post("/benchmark-runs", response_model=BenchmarkResponse, status_code=201)
def create_benchmark(payload: BenchmarkCreate, db: Session = Depends(get_db), user=WriteAccess):
    run = GenericRepository(db, BenchmarkRun).add(
        BenchmarkRun(
            solution_evaluated=payload.solution_evaluated,
            reference_competitors=payload.reference_competitors,
            gap_threshold=payload.gap_threshold,
        )
    )
    for axis in payload.axes:
        db.add(
            BenchmarkAxisScore(
                run_id=run.id,
                axis=axis.axis,
                our_score=axis.our_score,
                best_competitor_score=axis.best_competitor_score,
                gap=round(axis.our_score - axis.best_competitor_score, 2),
            )
        )
    db.flush()
    return _run_response(db, run)


@router.get("/benchmark-runs", response_model=list[BenchmarkResponse])
def list_benchmarks(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    return [_run_response(db, r) for r in GenericRepository(db, BenchmarkRun).list(skip, limit)]


@router.get("/benchmark-runs/{id}", response_model=BenchmarkResponse)
def get_benchmark(id: int, db: Session = Depends(get_db), user=AnyAuth):
    return _run_response(db, _get_run(db, id))


@router.post("/benchmark-runs/{id}/evaluate", response_model=BenchmarkResponse)
def evaluate_benchmark(id: int, db: Session = Depends(get_db), user=StrategyAccess):
    run = _get_run(db, id)
    axes = _axes(db, run.id)
    if not axes:
        raise AppError("error.validation", status_code=422)
    gaps = [a.gap for a in axes]
    run.differentiation_score = round(sum(max(-50.0, min(50.0, g)) for g in gaps) / len(gaps), 2)
    worst = min(axes, key=lambda a: a.gap)
    db.flush()
    if worst.gap < -run.gap_threshold:
        StrategyAdjustmentService().create(
            db,
            trigger_type="benchmark",
            decision=(
                f"Écart défavorable sur l'axe '{worst.axis}' (écart {worst.gap} < -seuil {run.gap_threshold}) "
                f"pour '{run.solution_evaluated}' : ajustement stratégique proposé"
            ),
            detail=f"benchmark:{run.id}:{worst.axis}",
        )
    return _run_response(db, run)


@router.get("/benchmark-runs/{id}/differentiation-score")
def differentiation_score(id: int, db: Session = Depends(get_db), user=AnyAuth):
    run = _get_run(db, id)
    axes = _axes(db, run.id)
    per_axis = {a.axis: a.gap for a in axes}
    return {
        "benchmark_run_id": run.id,
        "differentiation_score": run.differentiation_score,
        "gap_threshold": run.gap_threshold,
        "per_axis_gap": per_axis,
    }


@router.post("/strategy-adjustments", response_model=AdjustmentResponse, status_code=201)
def create_adjustment(payload: AdjustmentCreate, db: Session = Depends(get_db), user=StrategyAccess):
    adj = StrategyAdjustmentService().create(
        db,
        trigger_type=payload.trigger_type,
        decision=payload.decision,
        signal_id=payload.signal_id,
        advisory_insight_id=payload.advisory_insight_id,
        feedback_item_id=payload.feedback_item_id,
    )
    db.refresh(adj)
    return AdjustmentResponse(
        id=adj.id,
        trigger_type=adj.trigger_type,
        trigger_detail=adj.trigger_detail,
        signal_id=adj.signal_id,
        advisory_insight_id=adj.advisory_insight_id,
        feedback_item_id=adj.feedback_item_id,
        decision=adj.decision,
        applied_at=str(adj.applied_at) if adj.applied_at else None,
    )


@router.get("/strategy-adjustments", response_model=list[AdjustmentResponse])
def list_adjustments(trigger_type: str | None = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    stmt = select(StrategyAdjustment)
    if trigger_type:
        stmt = stmt.where(StrategyAdjustment.trigger_type == trigger_type)
    adjs = GenericRepository(db, StrategyAdjustment).list(skip, limit, stmt.order_by(StrategyAdjustment.id.desc()))
    return [
        AdjustmentResponse(
            id=a.id,
            trigger_type=a.trigger_type,
            trigger_detail=a.trigger_detail,
            signal_id=a.signal_id,
            advisory_insight_id=a.advisory_insight_id,
            feedback_item_id=a.feedback_item_id,
            decision=a.decision,
            applied_at=str(a.applied_at) if a.applied_at else None,
        )
        for a in adjs
    ]


@router.get("/strategy-adjustments/{id}/trace")
def trace_adjustment(id: int, db: Session = Depends(get_db), user=AnyAuth):
    return StrategyAdjustmentService().trace(db, id)
