from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import AnyAuth
from ..services.shared import ResponsibleAiService

router = APIRouter(tags=["socle-responsible-ai"])


@router.get("/responsible-ai/dashboard")
def responsible_ai_dashboard(db: Session = Depends(get_db), user=AnyAuth):
    return ResponsibleAiService().dashboard(db)
