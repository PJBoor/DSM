from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import AnyAuth, WriteAccess
from ..errors import AppError
from ..models import (
    CommunicationChannel,
    ContactPoint,
    Persona,
    Stakeholder,
    StakeholderPersona,
)
from ..repositories import GenericRepository
from ..security import utcnow

router = APIRouter(tags=["module2-decision-makers"])

MASK = "***"


class StakeholderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    role: str = Field(min_length=1, max_length=120)
    organization: str = Field(min_length=1, max_length=255)
    decision_level: int = Field(default=1, ge=1, le=5)
    budget_authority: bool = False


class StakeholderUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    organization: str | None = None
    decision_level: int | None = Field(default=None, ge=1, le=5)
    budget_authority: bool | None = None


class StakeholderResponse(BaseModel):
    id: int
    name: str
    role: str
    organization: str
    decision_level: int
    budget_authority: bool
    influence_score: float
    engagement_level: float

    model_config = {"from_attributes": True}


class PersonaCreate(BaseModel):
    role_type: str = Field(min_length=1, max_length=120)
    motivations: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    solution_preferences: list[str] = Field(default_factory=list)


class PersonaResponse(BaseModel):
    id: int
    role_type: str
    motivations: list
    pain_points: list
    success_criteria: list
    solution_preferences: list

    model_config = {"from_attributes": True}


class ChannelCreate(BaseModel):
    stakeholder_id: int
    type: str = Field(pattern="^(evenement|conference|linkedin|webinar)$")
    interaction_history: list = Field(default_factory=list)


class ChannelResponse(BaseModel):
    id: int
    stakeholder_id: int
    type: str
    interaction_history: list

    model_config = {"from_attributes": True}


class ContactPointCreate(BaseModel):
    channel_id: int | None = None
    at: datetime | None = None
    summary: str = ""


class ContactPointResponse(BaseModel):
    id: int
    stakeholder_id: int
    channel_id: int | None
    at: datetime
    summary: str

    model_config = {"from_attributes": True}


def _stakeholder_repo(db: Session) -> GenericRepository[Stakeholder]:
    return GenericRepository(db, Stakeholder)


def _get_stakeholder(db: Session, id: int) -> Stakeholder:
    obj = _stakeholder_repo(db).get(id)
    if obj is None:
        raise AppError("error.stakeholder_not_found", status_code=404, id=id, resource="stakeholder")
    return obj


def _get_persona(db: Session, id: int) -> Persona:
    obj = db.get(Persona, id)
    if obj is None:
        raise AppError("error.persona_not_found", status_code=404, id=id, resource="persona")
    return obj


def _recompute_scores(db: Session, stakeholder: Stakeholder) -> None:
    channels = list(
        db.execute(select(CommunicationChannel).where(CommunicationChannel.stakeholder_id == stakeholder.id)).scalars()
    )
    contacts = list(
        db.execute(select(ContactPoint).where(ContactPoint.stakeholder_id == stakeholder.id)).scalars()
    )
    recent = [c for c in contacts if (utcnow() - c.at).days <= 90]
    freq = min(1.0, len(recent) / 6.0)
    recency = max(0.0, 1.0 - (min((utcnow() - c.at).days for c in recent) / 90.0)) if recent else 0.0
    stakeholder.engagement_level = round(100 * (0.6 * freq + 0.4 * recency), 2)
    stakeholder.influence_score = round(
        100 * (0.5 * stakeholder.decision_level / 5 + 0.3 * (1 if stakeholder.budget_authority else 0) + 0.2 * min(1.0, len(channels) / 5)),
        2,
    )
    db.flush()


def _mask(response: StakeholderResponse, reader: bool) -> StakeholderResponse:
    if reader:
        response.name = MASK
        response.organization = MASK
    return response


def _is_reader(user) -> bool:
    return getattr(user, "role", "") == "reader"


@router.post("/stakeholders", response_model=StakeholderResponse, status_code=201)
def create_stakeholder(payload: StakeholderCreate, db: Session = Depends(get_db), user=WriteAccess):
    obj = _stakeholder_repo(db).add(Stakeholder(**payload.model_dump()))
    _recompute_scores(db, obj)
    db.refresh(obj)
    return obj


@router.get("/stakeholders", response_model=list[StakeholderResponse])
def list_stakeholders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    objs = _stakeholder_repo(db).list(skip, limit)
    return [_mask(StakeholderResponse.model_validate(o), _is_reader(user)) for o in objs]


@router.get("/stakeholders/{id}", response_model=StakeholderResponse)
def get_stakeholder(id: int, db: Session = Depends(get_db), user=AnyAuth):
    obj = _get_stakeholder(db, id)
    return _mask(StakeholderResponse.model_validate(obj), _is_reader(user))


@router.patch("/stakeholders/{id}", response_model=StakeholderResponse)
def update_stakeholder(id: int, payload: StakeholderUpdate, db: Session = Depends(get_db), user=WriteAccess):
    obj = _get_stakeholder(db, id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    _recompute_scores(db, obj)
    db.refresh(obj)
    return obj


@router.delete("/stakeholders/{id}", status_code=204)
def delete_stakeholder(id: int, db: Session = Depends(get_db), user=WriteAccess):
    _stakeholder_repo(db).delete(_get_stakeholder(db, id))


@router.get("/stakeholders/{id}/influence")
def get_influence(id: int, db: Session = Depends(get_db), user=AnyAuth):
    obj = _get_stakeholder(db, id)
    _recompute_scores(db, obj)
    return {"stakeholder_id": obj.id, "influence_score": obj.influence_score, "engagement_level": obj.engagement_level}


@router.post("/personas", response_model=PersonaResponse, status_code=201)
def create_persona(payload: PersonaCreate, db: Session = Depends(get_db), user=WriteAccess):
    if db.execute(select(Persona).where(Persona.role_type == payload.role_type)).first():
        raise AppError("error.duplicate", status_code=409, field=payload.role_type)
    return GenericRepository(db, Persona).add(Persona(**payload.model_dump()))


@router.get("/personas", response_model=list[PersonaResponse])
def list_personas(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    return GenericRepository(db, Persona).list(skip, limit)


@router.get("/personas/{id}", response_model=PersonaResponse)
def get_persona(id: int, db: Session = Depends(get_db), user=AnyAuth):
    return _get_persona(db, id)


@router.patch("/personas/{id}", response_model=PersonaResponse)
def update_persona(id: int, payload: PersonaCreate, db: Session = Depends(get_db), user=WriteAccess):
    obj = _get_persona(db, id)
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    db.flush()
    db.refresh(obj)
    return obj


@router.delete("/personas/{id}", status_code=204)
def delete_persona(id: int, db: Session = Depends(get_db), user=WriteAccess):
    GenericRepository(db, Persona).delete(_get_persona(db, id))


def _fit_score(stakeholder: Stakeholder, persona: Persona) -> float:
    role_match = 1.0 if stakeholder.role.lower() in persona.role_type.lower() or persona.role_type.lower() in stakeholder.role.lower() else 0.3
    return round(100 * (0.7 * role_match + 0.3 * stakeholder.decision_level / 5), 2)


@router.put("/stakeholders/{id}/personas/{persona_id}")
def associate_persona(id: int, persona_id: int, db: Session = Depends(get_db), user=WriteAccess):
    stakeholder = _get_stakeholder(db, id)
    persona = _get_persona(db, persona_id)
    assoc = db.get(StakeholderPersona, (stakeholder.id, persona.id))
    if assoc is None:
        assoc = StakeholderPersona(stakeholder_id=stakeholder.id, persona_id=persona.id)
        db.add(assoc)
    assoc.fit_score = _fit_score(stakeholder, persona)
    db.flush()
    return {"stakeholder_id": stakeholder.id, "persona_id": persona.id, "fit_score": assoc.fit_score}


@router.delete("/stakeholders/{id}/personas/{persona_id}", status_code=204)
def dissociate_persona(id: int, persona_id: int, db: Session = Depends(get_db), user=WriteAccess):
    assoc = db.get(StakeholderPersona, (id, persona_id))
    if assoc is None:
        raise AppError("error.not_found", status_code=404, resource="association", id=persona_id)
    db.delete(assoc)
    db.flush()


@router.get("/stakeholders/{id}/recommended-persona")
def recommended_persona(id: int, db: Session = Depends(get_db), user=AnyAuth):
    stakeholder = _get_stakeholder(db, id)
    assocs = list(db.execute(select(StakeholderPersona).where(StakeholderPersona.stakeholder_id == id)).scalars())
    if assocs:
        best = max(assocs, key=lambda a: a.fit_score)
        persona = db.get(Persona, best.persona_id)
        return {"stakeholder_id": id, "persona": PersonaResponse.model_validate(persona), "fit_score": best.fit_score, "source": "association"}
    personas = list(db.execute(select(Persona)).scalars())
    if not personas:
        raise AppError("error.persona_not_found", status_code=404, id=0, resource="persona")
    best_persona = max(personas, key=lambda p: _fit_score(stakeholder, p))
    return {"stakeholder_id": id, "persona": PersonaResponse.model_validate(best_persona), "fit_score": _fit_score(stakeholder, best_persona), "source": "computed"}


@router.post("/channels", response_model=ChannelResponse, status_code=201)
def create_channel(payload: ChannelCreate, db: Session = Depends(get_db), user=WriteAccess):
    _get_stakeholder(db, payload.stakeholder_id)
    return GenericRepository(db, CommunicationChannel).add(CommunicationChannel(**payload.model_dump()))


@router.get("/channels", response_model=list[ChannelResponse])
def list_channels(stakeholder_id: int | None = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    stmt = select(CommunicationChannel)
    if stakeholder_id is not None:
        stmt = stmt.where(CommunicationChannel.stakeholder_id == stakeholder_id)
    return GenericRepository(db, CommunicationChannel).list(skip, limit, stmt)


@router.post("/stakeholders/{id}/contact-points", response_model=ContactPointResponse, status_code=201)
def add_contact_point(id: int, payload: ContactPointCreate, db: Session = Depends(get_db), user=WriteAccess):
    stakeholder = _get_stakeholder(db, id)
    if payload.channel_id is not None and db.get(CommunicationChannel, payload.channel_id) is None:
        raise AppError("error.not_found", status_code=404, resource="channel", id=payload.channel_id)
    cp = ContactPoint(stakeholder_id=stakeholder.id, channel_id=payload.channel_id, at=payload.at or utcnow(), summary=payload.summary)
    db.add(cp)
    db.flush()
    _recompute_scores(db, stakeholder)
    db.refresh(cp)
    return cp


@router.get("/stakeholders/{id}/contact-points", response_model=list[ContactPointResponse])
def list_contact_points(id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    _get_stakeholder(db, id)
    stmt = select(ContactPoint).where(ContactPoint.stakeholder_id == id).order_by(ContactPoint.at.desc())
    return GenericRepository(db, ContactPoint).list(skip, limit, stmt)
