"""Services partagés explicitement identifiés (anti-duplication inter-modules).

- SignalScoringService      : score de pertinence (module 1), consommé par le module 5
- StrategyAdjustmentService : création/traçabilité des ajustements (modules 1, 5, 6, 8)
- RoiCalculatorService      : calculateur de ROI (module 4)
- RelationshipHealthService : score de santé de relation (module 7)
- KpiEvaluationService      : écart KPI -> FeedbackItem -> ajustement module 5 (module 8)
- BudgetGuardService        : contrôle allocation / contingence (module 9)
- ResponsibleAiService      : socle transverse, gate de publication
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..errors import AppError
from ..models import (
    AppConfig,
    BudgetLine,
    Competitor,
    Contingency,
    ContingencyDraw,
    FeedbackItem,
    KpiAlert,
    KPI,
    MarketSignal,
    NetworkContact,
    Interaction,
    SectorSolution,
    SignalAlert,
    StrategyAdjustment,
    PilotProgram,
)
from ..repositories import config_get, config_set
from ..security import utcnow

SIGNAL_TYPE_WEIGHTS = {
    "investissement": 1.0,
    "lancement": 0.9,
    "partenariat": 0.7,
    "campagne": 0.5,
}

SENTIMENT_SCORES = {"positif": 1.0, "neutre": 0.5, "negatif": 0.1}

PILOT_TRANSITIONS = {
    "planned": {"running", "cancelled"},
    "running": {"completed", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


class SignalScoringService:
    """Score de pertinence = 50% récence + 30% type + 20% position concurrentielle (0-100)."""

    def score(self, signal_date: date, signal_type: str, market_share: float, now: date | None = None) -> float:
        now = now or utcnow().date()
        days = max(0, (now - signal_date).days)
        recency = max(0.0, 1.0 - days / 365.0)
        type_w = SIGNAL_TYPE_WEIGHTS.get(signal_type, 0.5)
        position = min(1.0, max(0.0, market_share))
        return round(100.0 * (0.5 * recency + 0.3 * type_w + 0.2 * position), 2)

    def threshold(self, db: Session) -> float:
        return float(config_get(db, "signal_alert_threshold", str(settings.DEFAULT_SIGNAL_ALERT_THRESHOLD)))

    def set_threshold(self, db: Session, value: float) -> None:
        config_set(db, "signal_alert_threshold", str(value))

    def evaluate(self, db: Session, signal: MarketSignal) -> SignalAlert | None:
        competitor = db.get(Competitor, signal.competitor_id)
        signal.relevance_score = self.score(signal.date, signal.type, competitor.market_share if competitor else 0.0)
        db.flush()
        threshold = self.threshold(db)
        if signal.relevance_score >= threshold:
            alert = SignalAlert(signal_id=signal.id, threshold=threshold)
            db.add(alert)
            db.flush()
            StrategyAdjustmentService().create(
                db,
                trigger_type="signal",
                decision=f"Signal #{signal.id} ({signal.type}) de pertinence {signal.relevance_score} >= seuil {threshold}",
                signal_id=signal.id,
                detail=f"signal:{signal.id}",
            )
            return alert
        return None


class StrategyAdjustmentService:
    def create(
        self,
        db: Session,
        trigger_type: str,
        decision: str,
        signal_id: int | None = None,
        advisory_insight_id: int | None = None,
        feedback_item_id: int | None = None,
        detail: str = "",
        applied_at: date | None = None,
    ) -> StrategyAdjustment:
        adj = StrategyAdjustment(
            trigger_type=trigger_type,
            trigger_detail=detail,
            signal_id=signal_id,
            advisory_insight_id=advisory_insight_id,
            feedback_item_id=feedback_item_id,
            decision=decision,
            applied_at=applied_at or utcnow().date(),
        )
        db.add(adj)
        db.flush()
        return adj

    def trace(self, db: Session, adjustment_id: int) -> dict:
        adj = db.get(StrategyAdjustment, adjustment_id)
        if adj is None:
            raise AppError("error.adjustment_not_found", status_code=404, id=adjustment_id)
        cause: dict = {"trigger_type": adj.trigger_type, "trigger_detail": adj.trigger_detail}
        if adj.signal_id:
            sig = db.get(MarketSignal, adj.signal_id)
            cause["signal"] = (
                {"id": sig.id, "type": sig.type, "date": str(sig.date), "relevance_score": sig.relevance_score}
                if sig
                else {"id": adj.signal_id, "deleted": True}
            )
        if adj.advisory_insight_id:
            from ..models import AdvisoryInsight

            ins = db.get(AdvisoryInsight, adj.advisory_insight_id)
            cause["advisory_insight"] = (
                {"id": ins.id, "recommendation": ins.recommendation, "domain": ins.domain, "status": ins.status}
                if ins
                else {"id": adj.advisory_insight_id, "deleted": True}
            )
        if adj.feedback_item_id:
            fb = db.get(FeedbackItem, adj.feedback_item_id)
            cause["feedback_item"] = (
                {"id": fb.id, "source": fb.source, "criticality": fb.criticality, "need": fb.need}
                if fb
                else {"id": adj.feedback_item_id, "deleted": True}
            )
        return {
            "adjustment_id": adj.id,
            "decision": adj.decision,
            "applied_at": str(adj.applied_at) if adj.applied_at else None,
            "created_at": adj.created_at.isoformat(),
            "cause": cause,
        }


class RoiCalculatorService:
    """Entrées : initial_cost, annual_cost, annual_gain, horizon_months.

    Sorties : ROI (%) sur l'horizon, délai de retour (mois), niveau de risque.
    """

    def calculate(self, initial_cost: float, annual_cost: float, annual_gain: float, horizon_months: int) -> dict:
        years = horizon_months / 12.0
        total_cost = initial_cost + annual_cost * years
        total_gain = annual_gain * years
        roi = round(((total_gain - total_cost) / total_cost) * 100.0, 2) if total_cost > 0 else 0.0
        monthly_net = (annual_gain - annual_cost) / 12.0
        payback = round(initial_cost / monthly_net, 2) if monthly_net > 0 else None
        risks: list[str] = []
        if payback is None or payback > horizon_months or roi < 0:
            risk = "high"
            risks.append("payback beyond horizon" if payback is not None else "never pays back")
        elif payback > 0.75 * horizon_months:
            risk = "medium"
            risks.append("payback close to horizon end")
        else:
            risk = "low"
        if annual_gain <= 0:
            risks.append("no projected gain")
        return {
            "roi_percent": roi,
            "payback_months": payback,
            "risk_level": risk,
            "risk_indicators": risks,
            "total_cost": round(total_cost, 2),
            "total_gain": round(total_gain, 2),
        }


class RelationshipHealthService:
    """Santé = 40% fréquence + 30% récence + 30% sentiment (0-100), fenêtre 180 jours."""

    WINDOW_DAYS = 180

    def reengagement_delay_days(self, influence: float) -> int:
        if influence >= 0.7:
            return 30
        if influence >= 0.4:
            return 60
        return 90

    def health(self, contact: NetworkContact, interactions: list[Interaction], now=None) -> float:
        now = now or utcnow()
        recent = [i for i in interactions if (now - i.date).days <= self.WINDOW_DAYS]
        frequency = min(1.0, len(recent) / 10.0)
        if recent:
            last = max(i.date for i in recent)
            recency = max(0.0, 1.0 - (now - last).days / self.WINDOW_DAYS)
        else:
            recency = 0.0
        sentiment = (
            sum(SENTIMENT_SCORES.get(i.sentiment, 0.5) for i in recent) / len(recent) if recent else 0.0
        )
        return round(100.0 * (0.4 * frequency + 0.3 * recency + 0.3 * sentiment), 2)

    def recompute(self, db: Session, contact: NetworkContact) -> float:
        interactions = list(
            db.execute(select(Interaction).where(Interaction.contact_id == contact.id)).scalars().all()
        )
        contact.health_score = self.health(contact, interactions)
        db.flush()
        return contact.health_score

    def reengagement_alerts(self, db: Session) -> list[dict]:
        alerts = []
        contacts = list(db.execute(select(NetworkContact)).scalars().all())
        for c in contacts:
            interactions = list(
                db.execute(select(Interaction).where(Interaction.contact_id == c.id)).scalars().all()
            )
            if not interactions:
                alerts.append({"contact_id": c.id, "days_since_last_contact": None, "required_delay": self.reengagement_delay_days(c.influence)})
                continue
            days = (utcnow() - max(i.date for i in interactions)).days
            required = self.reengagement_delay_days(c.influence)
            if days > required:
                alerts.append({"contact_id": c.id, "days_since_last_contact": days, "required_delay": required})
        return alerts


class KpiEvaluationService:
    def threshold(self, db: Session) -> float:
        return float(config_get(db, "kpi_deviation_threshold", str(settings.DEFAULT_KPI_DEVIATION_THRESHOLD)))

    def set_threshold(self, db: Session, value: float) -> None:
        config_set(db, "kpi_deviation_threshold", str(value))

    def deviation(self, kpi: KPI) -> float:
        if kpi.target == 0:
            return 0.0 if kpi.value == 0 else float("inf")
        return (kpi.value - kpi.target) / kpi.target

    def evaluate(self, db: Session, kpi: KPI) -> KpiAlert | None:
        dev = self.deviation(kpi)
        threshold = self.threshold(db)
        if abs(dev) <= threshold:
            return None
        criticality = "high" if abs(dev) > 2 * threshold else "medium"
        fb = FeedbackItem(
            source="kpi",
            verbatim=f"KPI {kpi.type} ({kpi.period}) : valeur {kpi.value} vs cible {kpi.target}",
            need=f"Corriger l'écart de {round(dev * 100, 2)}% sur le KPI {kpi.type}",
            criticality=criticality,
            status="open",
        )
        db.add(fb)
        db.flush()
        adj = StrategyAdjustmentService().create(
            db,
            trigger_type="kpi_gap",
            decision=f"Ajustement déclenché par l'écart du KPI {kpi.type} ({kpi.period}), écart {round(dev * 100, 2)}%",
            feedback_item_id=fb.id,
            detail=f"kpi:{kpi.id}",
        )
        fb.linked_adjustment_id = adj.id
        alert = KpiAlert(kpi_id=kpi.id, deviation=round(dev, 4) if dev != float("inf") else 999.0, feedback_item_id=fb.id)
        db.add(alert)
        db.flush()
        return alert


class BudgetGuardService:
    """Règle métier : aucune consommation au-delà de l'allocation sans provision de contingence mobilisée."""

    def cap(self, db: Session) -> float:
        return float(config_get(db, "contingency_cap", str(settings.DEFAULT_CONTINGENCY_CAP)))

    def reserve(self, db: Session) -> dict:
        total_prov = float(db.execute(select(func.sum(Contingency.provision))).scalar_one() or 0.0)
        total_drawn = float(db.execute(select(func.sum(Contingency.drawn))).scalar_one() or 0.0)
        cap = self.cap(db)
        return {
            "cap": cap,
            "total_provision": round(total_prov, 2),
            "total_drawn": round(total_drawn, 2),
            "remaining": round(total_prov - total_drawn, 2),
        }

    def add_contingency(self, db: Session, contingency: Contingency) -> None:
        reserve = self.reserve(db)
        if reserve["total_provision"] + contingency.provision > reserve["cap"]:
            raise AppError("error.contingency_cap_reached", status_code=409, cap=reserve["cap"])

    def consume(self, db: Session, line: BudgetLine, amount: float, justification: str = "") -> dict:
        if amount <= 0:
            raise AppError("error.validation", status_code=422)
        projected = line.consumed + amount
        if projected <= line.allocated:
            line.consumed = round(projected, 2)
            db.flush()
            return {"budget_line_id": line.id, "consumed": line.consumed, "contingency_drawn": 0.0}
        overage = round(projected - line.allocated, 2)
        reserve = self.reserve(db)
        if reserve["remaining"] < overage:
            raise AppError("error.budget_exceeded", status_code=409, overage=overage)
        remaining_needed = overage
        for contingency in db.execute(select(Contingency).order_by(Contingency.provision.desc())).scalars():
            available = contingency.provision - contingency.drawn
            if available <= 0:
                continue
            take = min(available, remaining_needed)
            contingency.drawn = round(contingency.drawn + take, 2)
            draw = ContingencyDraw(
                budget_line_id=line.id,
                contingency_id=contingency.id,
                amount=round(take, 2),
                justification=justification or f"Dépassement de la ligne budgétaire #{line.id}",
            )
            db.add(draw)
            remaining_needed = round(remaining_needed - take, 2)
            if remaining_needed <= 0:
                break
        line.consumed = round(projected, 2)
        db.flush()
        return {"budget_line_id": line.id, "consumed": line.consumed, "contingency_drawn": overage}

    def report(self, db: Session, fiscal_year: int | None = None) -> list[dict]:
        stmt = select(BudgetLine)
        if fiscal_year is not None:
            stmt = stmt.where(BudgetLine.fiscal_year == fiscal_year)
        lines = list(db.execute(stmt).scalars().all())
        report = []
        for line in lines:
            utilization = (line.consumed / line.allocated) if line.allocated > 0 else 0.0
            report.append(
                {
                    "budget_line_id": line.id,
                    "pillar": line.pillar,
                    "fiscal_year": line.fiscal_year,
                    "allocated": line.allocated,
                    "consumed": line.consumed,
                    "utilization": round(utilization, 4),
                    "alert": "over_budget" if line.consumed > line.allocated else ("high_utilization" if utilization > 0.9 else None),
                }
            )
        return report


class ResponsibleAiService:
    """Socle transverse : champs éthiques obligatoires et gate de publication."""

    OPEN_PRIVACY_LEVELS = {"high", "medium"}

    def dashboard(self, db: Session) -> dict:
        solutions = list(db.execute(select(SectorSolution)).scalars().all())
        pilots = list(db.execute(select(PilotProgram)).scalars().all())
        return {
            "sector_solutions_total": len(solutions),
            "ethics_validated": sum(1 for s in solutions if s.ethics_status == "validated"),
            "ethics_pending": sum(1 for s in solutions if s.ethics_status != "validated"),
            "privacy_impacts_open": sum(
                1
                for s in solutions + [p for p in pilots]  # type: ignore[attr-defined]
                if getattr(s, "privacy_impact_level", "unknown") in self.OPEN_PRIVACY_LEVELS
                and not getattr(s, "privacy_measures", [])
            ),
            "fairness_missing": sum(1 for s in solutions + pilots if s.fairness_status == "missing"),
            "pilots_total": len(pilots),
            "pilots_missing_ethics": sum(1 for p in pilots if p.ethics_review_status != "validated"),
        }

    def assert_publishable(self, solution: SectorSolution) -> None:
        if solution.ethics_status != "validated":
            raise AppError("error.ethics_review_required", status_code=409)


class PilotLifecycleService:
    def transition(self, pilot: PilotProgram, to_status: str) -> None:
        allowed = PILOT_TRANSITIONS.get(pilot.status, set())
        if to_status not in allowed:
            raise AppError(
                "error.invalid_transition", status_code=409, from_status=pilot.status, to_status=to_status
            )
        pilot.status = to_status
