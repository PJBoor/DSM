from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import AnyAuth, WriteAccess
from ..errors import AppError
from ..models import Interaction, NetworkContact, Opportunity, Partnership
from ..repositories import GenericRepository
from ..services.shared import RelationshipHealthService

router = APIRouter(tags=["module7-network-crm"])

MASK = "***"


class ContactCreate(BaseModel):
    organization: str = Field(min_length=1, max_length=255)
    sector: str = Field(min_length=1, max_length=120)
    influence: float = Field(default=0.0, ge=0.0, le=1.0)


class ContactResponse(BaseModel):
    id: int
    organization: str
    sector: str
    influence: float
    health_score: float

    model_config = {"from_attributes": True}


class InteractionCreate(BaseModel):
    type: str = Field(min_length=1, max_length=60)
    date: datetime | None = None
    report: str = ""
    sentiment: str = Field(default="neutre", pattern="^(positif|neutre|negatif)$")


class InteractionResponse(BaseModel):
    id: int
    contact_id: int
    type: str
    date: datetime
    report: str
    sentiment: str

    model_config = {"from_attributes": True}


class PartnershipCreate(BaseModel):
    partner: str = Field(min_length=1, max_length=255)
    objective: str = ""
    co_developments: list[str] = Field(default_factory=list)
    target_markets: list[str] = Field(default_factory=list)
    status: str = Field(default="active")


class PartnershipResponse(BaseModel):
    id: int
    partner: str
    objective: str
    co_developments: list
    target_markets: list
    status: str

    model_config = {"from_attributes": True}


class OpportunityCreate(BaseModel):
    contact_id: int
    description: str = ""
    stage: str = Field(default="identified")
    value: float = Field(default=0.0, ge=0)


class OpportunityResponse(BaseModel):
    id: int
    contact_id: int
    description: str
    stage: str
    value: float

    model_config = {"from_attributes": True}


def _get_contact(db: Session, id: int) -> NetworkContact:
    obj = db.get(NetworkContact, id)
    if obj is None:
        raise AppError("error.contact_not_found", status_code=404, id=id, resource="network_contact")
    return obj


def _mask(c: ContactResponse, reader: bool) -> ContactResponse:
    if reader:
        c.organization = MASK
    return c


def _is_reader(user) -> bool:
    return getattr(user, "role", "") == "reader"


@router.post("/network-contacts", response_model=ContactResponse, status_code=201)
def create_contact(payload: ContactCreate, db: Session = Depends(get_db), user=WriteAccess):
    return GenericRepository(db, NetworkContact).add(NetworkContact(**payload.model_dump()))


@router.get("/network-contacts", response_model=list[ContactResponse])
def list_contacts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    objs = GenericRepository(db, NetworkContact).list(skip, limit)
    return [_mask(ContactResponse.model_validate(o), _is_reader(user)) for o in objs]


@router.get("/network-contacts/{id}", response_model=ContactResponse)
def get_contact(id: int, db: Session = Depends(get_db), user=AnyAuth):
    return _mask(ContactResponse.model_validate(_get_contact(db, id)), _is_reader(user))


@router.delete("/network-contacts/{id}", status_code=204)
def delete_contact(id: int, db: Session = Depends(get_db), user=WriteAccess):
    GenericRepository(db, NetworkContact).delete(_get_contact(db, id))


@router.post("/network-contacts/{id}/interactions", response_model=InteractionResponse, status_code=201)
def add_interaction(id: int, payload: InteractionCreate, db: Session = Depends(get_db), user=WriteAccess):
    contact = _get_contact(db, id)
    inter = Interaction(contact_id=contact.id, type=payload.type, date=payload.date or datetime.utcnow(), report=payload.report, sentiment=payload.sentiment)
    db.add(inter)
    db.flush()
    RelationshipHealthService().recompute(db, contact)
    db.refresh(inter)
    return inter


@router.get("/network-contacts/{id}/interactions", response_model=list[InteractionResponse])
def list_interactions(id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    _get_contact(db, id)
    stmt = select(Interaction).where(Interaction.contact_id == id).order_by(Interaction.date.desc())
    return GenericRepository(db, Interaction).list(skip, limit, stmt)


@router.get("/network-contacts/{id}/health-score")
def health_score(id: int, db: Session = Depends(get_db), user=AnyAuth):
    contact = _get_contact(db, id)
    score = RelationshipHealthService().recompute(db, contact)
    return {"contact_id": contact.id, "health_score": score, "required_reengagement_delay_days": RelationshipHealthService().reengagement_delay_days(contact.influence)}


@router.get("/reengagement-alerts")
def reengagement_alerts(db: Session = Depends(get_db), user=AnyAuth):
    return {"alerts": RelationshipHealthService().reengagement_alerts(db)}


@router.post("/partnerships", response_model=PartnershipResponse, status_code=201)
def create_partnership(payload: PartnershipCreate, db: Session = Depends(get_db), user=WriteAccess):
    return GenericRepository(db, Partnership).add(Partnership(**payload.model_dump()))


@router.get("/partnerships", response_model=list[PartnershipResponse])
def list_partnerships(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    return GenericRepository(db, Partnership).list(skip, limit)


@router.post("/opportunities", response_model=OpportunityResponse, status_code=201)
def create_opportunity(payload: OpportunityCreate, db: Session = Depends(get_db), user=WriteAccess):
    _get_contact(db, payload.contact_id)
    return GenericRepository(db, Opportunity).add(Opportunity(**payload.model_dump()))


@router.get("/opportunities", response_model=list[OpportunityResponse])
def list_opportunities(contact_id: int | None = None, stage: str | None = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    stmt = select(Opportunity)
    if contact_id is not None:
        stmt = stmt.where(Opportunity.contact_id == contact_id)
    if stage:
        stmt = stmt.where(Opportunity.stage == stage)
    return GenericRepository(db, Opportunity).list(skip, limit, stmt)
