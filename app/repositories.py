from typing import Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from .database import Base
from .models import AppConfig

ModelT = TypeVar("ModelT", bound=Base)


class GenericRepository(Generic[ModelT]):
    def __init__(self, db: Session, model: type[ModelT]):
        self.db = db
        self.model = model

    def get(self, id: int) -> ModelT | None:
        return self.db.get(self.model, id)

    def list(self, skip: int = 0, limit: int = 100, stmt: Select | None = None) -> list[ModelT]:
        stmt = stmt if stmt is not None else select(self.model)
        return list(self.db.execute(stmt.offset(skip).limit(limit)).scalars().all())

    def count(self, stmt: Select | None = None) -> int:
        stmt = stmt if stmt is not None else select(func.count()).select_from(self.model)
        return int(self.db.execute(stmt).scalar_one())

    def add(self, obj: ModelT) -> ModelT:
        self.db.add(obj)
        self.db.flush()
        self.db.refresh(obj)
        return obj

    def delete(self, obj: ModelT) -> None:
        self.db.delete(obj)
        self.db.flush()


def config_get(db: Session, key: str, default: str) -> str:
    row = db.get(AppConfig, key)
    return row.value if row else default


def config_set(db: Session, key: str, value: str) -> None:
    row = db.get(AppConfig, key)
    if row is None:
        row = AppConfig(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.flush()
