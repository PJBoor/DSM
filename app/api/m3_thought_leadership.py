from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import AnyAuth, WriteAccess
from ..models import Citation, EventParticipation, InfluencerRelationship, Publication
from ..repositories import GenericRepository

router = APIRouter(tags=["module3-thought-leadership"])


class PublicationCreate(BaseModel):
    type: str = Field(pattern="^(livre_blanc|article_recherche|blog|webinar)$")
    date: date
    theme: str = Field(min_length=1, max_length=255)
    reach_metrics: dict = Field(default_factory=dict)


class PublicationResponse(BaseModel):
    id: int
    type: str
    date: date
    theme: str
    reach_metrics: dict

    model_config = {"from_attributes": True}


class EventCreate(BaseModel):
    event: str = Field(min_length=1, max_length=255)
    format: str = Field(pattern="^(keynote|panel|webinar)$")
    date: date
    decision_makers_met: list[str] = Field(default_factory=list)


class EventResponse(BaseModel):
    id: int
    event: str
    format: str
    date: date
    decision_makers_met: list

    model_config = {"from_attributes": True}


class InfluencerCreate(BaseModel):
    kind: str = Field(pattern="^(analyste|media)$")
    organization: str = Field(min_length=1, max_length=255)
    trust_level: int = Field(default=3, ge=1, le=5)
    exchange_history: list = Field(default_factory=list)


class InfluencerResponse(BaseModel):
    id: int
    kind: str
    organization: str
    trust_level: int
    exchange_history: list

    model_config = {"from_attributes": True}


class CitationCreate(BaseModel):
    publication_id: int
    source: str = Field(min_length=1, max_length=255)
    date: date


class CitationResponse(BaseModel):
    id: int
    publication_id: int
    source: str
    date: date

    model_config = {"from_attributes": True}


def _crud_list(repo_model, db, skip, limit):
    return GenericRepository(db, repo_model).list(skip, limit)


@router.post("/publications", response_model=PublicationResponse, status_code=201)
def create_publication(payload: PublicationCreate, db: Session = Depends(get_db), user=WriteAccess):
    return GenericRepository(db, Publication).add(Publication(**payload.model_dump()))


@router.get("/publications", response_model=list[PublicationResponse])
def list_publications(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    return _crud_list(Publication, db, skip, limit)


@router.get("/publications/{id}", response_model=PublicationResponse)
def get_publication(id: int, db: Session = Depends(get_db), user=AnyAuth):
    return GenericRepository(db, Publication).get(id)


@router.delete("/publications/{id}", status_code=204)
def delete_publication(id: int, db: Session = Depends(get_db), user=WriteAccess):
    obj = GenericRepository(db, Publication).get(id)
    if obj:
        GenericRepository(db, Publication).delete(obj)


@router.post("/event-participations", response_model=EventResponse, status_code=201)
def create_event(payload: EventCreate, db: Session = Depends(get_db), user=WriteAccess):
    return GenericRepository(db, EventParticipation).add(EventParticipation(**payload.model_dump()))


@router.get("/event-participations", response_model=list[EventResponse])
def list_events(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    return _crud_list(EventParticipation, db, skip, limit)


@router.post("/influencer-relationships", response_model=InfluencerResponse, status_code=201)
def create_influencer(payload: InfluencerCreate, db: Session = Depends(get_db), user=WriteAccess):
    return GenericRepository(db, InfluencerRelationship).add(InfluencerRelationship(**payload.model_dump()))


@router.get("/influencer-relationships", response_model=list[InfluencerResponse])
def list_influencers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    return _crud_list(InfluencerRelationship, db, skip, limit)


@router.post("/citations", response_model=CitationResponse, status_code=201)
def create_citation(payload: CitationCreate, db: Session = Depends(get_db), user=WriteAccess):
    return GenericRepository(db, Citation).add(Citation(**payload.model_dump()))


@router.get("/citations", response_model=list[CitationResponse])
def list_citations(publication_id: int | None = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), user=AnyAuth):
    stmt = select(Citation)
    if publication_id is not None:
        stmt = stmt.where(Citation.publication_id == publication_id)
    return GenericRepository(db, Citation).list(skip, limit, stmt)


@router.get("/thought-leadership/index")
def thought_leadership_index(db: Session = Depends(get_db), user=AnyAuth):
    pubs = list(db.execute(select(Publication)).scalars())
    citations = list(db.execute(select(Citation)).scalars())
    events = list(db.execute(select(EventParticipation)).scalars())
    rels = list(db.execute(select(InfluencerRelationship)).scalars())
    pub_component = min(1.0, (len(pubs) + len(citations)) / 20.0)
    participants = sum(len(e.decision_makers_met or []) for e in events)
    event_component = min(1.0, participants / 30.0)
    if rels:
        rel_component = min(1.0, (sum(r.trust_level for r in rels) / len(rels) / 5.0) * (len(rels) / 10.0))
    else:
        rel_component = 0.0
    index = round(100 * (0.4 * pub_component + 0.3 * event_component + 0.3 * rel_component), 2)
    return {
        "index": index,
        "components": {
            "publications": {"count": len(pubs), "citations": len(citations), "score": round(pub_component, 4)},
            "events": {"count": len(events), "decision_makers_met": participants, "score": round(event_component, 4)},
            "influencer_relationships": {"count": len(rels), "score": round(rel_component, 4)},
        },
    }
