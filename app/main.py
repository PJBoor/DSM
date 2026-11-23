from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import engine, get_db
from .deps import get_locale
from .errors import register_handlers
from .i18n import t
from .logging_conf import CorrelationIdMiddleware, configure_logging

configure_logging()

from .api import auth, m1_market, m2_decision_makers, m3_thought_leadership, m4_tailoring, m5_benchmark, m6_advisory, m7_network, m8_feedback, m9_finance, responsible_ai  # noqa: E402

app = FastAPI(
    title="Holistic Approach API",
    version="1.0.0",
    description=(
        "API backend de la démarche holistique d'entrée sur le marché de l'IA : "
        "neuf piliers métier (veille concurrentielle, décideurs, leadership d'opinion, "
        "personnalisation, benchmarking, conseils consultatifs, réseau/CRM, boucle de retour, "
        "budget) et un socle transverse d'IA responsable. Bilingue fr/en (Accept-Language)."
    ),
)

app.add_middleware(CorrelationIdMiddleware)
register_handlers(app)

app.include_router(auth.router)
app.include_router(m1_market.router)
app.include_router(m2_decision_makers.router)
app.include_router(m3_thought_leadership.router)
app.include_router(m4_tailoring.router)
app.include_router(m5_benchmark.router)
app.include_router(m6_advisory.router)
app.include_router(m7_network.router)
app.include_router(m8_feedback.router)
app.include_router(m9_finance.router)
app.include_router(responsible_ai.router)


@app.get("/health", tags=["socle"])
def health(locale: str = Depends(get_locale)):
    return {"status": t("health.ok", locale)}


@app.get("/ready", tags=["socle"])
def ready(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ready", "database": engine.url.get_backend_name()}


@app.get("/", tags=["socle"])
def root():
    return {"name": "Holistic Approach API", "ui": "/ui/", "docs": "/docs", "openapi": "/openapi.json"}


_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/ui", StaticFiles(directory=_static_dir, html=True), name="ui")
