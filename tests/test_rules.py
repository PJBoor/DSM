"""Tests unitaires des règles métier (services partagés)."""

from datetime import date, timedelta

import pytest

from app.errors import AppError
from app.models import (
    BudgetLine,
    Competitor,
    Contingency,
    ContingencyDraw,
    Interaction,
    KPI,
    MarketSignal,
    NetworkContact,
    PilotProgram,
    SectorSolution,
    Stakeholder,
)
from app.security import utcnow
from app.services.shared import (
    BudgetGuardService,
    KpiEvaluationService,
    PilotLifecycleService,
    RelationshipHealthService,
    RoiCalculatorService,
    SignalScoringService,
)


class TestSignalScoring:
    def test_score_combines_recency_type_position(self, db_session):
        svc = SignalScoringService()
        today = date.today()
        score = svc.score(today, "investissement", 0.8, now=today)
        assert score == round(100 * (0.5 * 1.0 + 0.3 * 1.0 + 0.2 * 0.8), 2)

    def test_old_signal_scores_lower(self):
        svc = SignalScoringService()
        today = date.today()
        recent = svc.score(today, "investissement", 0.5, now=today)
        old = svc.score(today - timedelta(days=300), "campagne", 0.1, now=today)
        assert recent > old

    def test_alert_and_adjustment_when_above_threshold(self, db_session):
        comp = Competitor(name="BigCorp", sector="IA", market_share=0.9)
        db_session.add(comp)
        db_session.flush()
        signal = MarketSignal(competitor_id=comp.id, type="investissement", source="presse", date=date.today())
        db_session.add(signal)
        db_session.flush()
        alert = SignalScoringService().evaluate(db_session, signal)
        assert alert is not None
        assert signal.relevance_score >= 70.0
        db_session.commit()
        from app.models import StrategyAdjustment

        adj = db_session.query(StrategyAdjustment).filter_by(signal_id=signal.id).one()
        assert adj.trigger_type == "signal"

    def test_no_alert_below_threshold(self, db_session):
        comp = Competitor(name="SmallCorp", sector="IA", market_share=0.01)
        db_session.add(comp)
        db_session.flush()
        signal = MarketSignal(
            competitor_id=comp.id, type="campagne", source="presse", date=date.today() - timedelta(days=360)
        )
        db_session.add(signal)
        db_session.flush()
        assert SignalScoringService().evaluate(db_session, signal) is None


class TestRoiCalculator:
    def test_roi_payback_risk(self):
        result = RoiCalculatorService().calculate(
            initial_cost=100000, annual_cost=20000, annual_gain=60000, horizon_months=36
        )
        assert result["total_cost"] == 160000
        assert result["total_gain"] == 180000
        assert result["roi_percent"] == 12.5
        assert result["payback_months"] == 30.0
        assert result["risk_level"] == "medium"

    def test_never_pays_back_is_high_risk(self):
        result = RoiCalculatorService().calculate(100000, 50000, 40000, 24)
        assert result["payback_months"] is None
        assert result["risk_level"] == "high"


class TestRelationshipHealth:
    def test_healthy_contact_scores_high(self, db_session):
        contact = NetworkContact(organization="Org", sector="finance", influence=0.9)
        db_session.add(contact)
        db_session.flush()
        for i in range(5):
            db_session.add(
                Interaction(
                    contact_id=contact.id,
                    type="reunion",
                    date=utcnow() - timedelta(days=5 * i + 1),
                    report="ok",
                    sentiment="positif",
                )
            )
        db_session.flush()
        score = RelationshipHealthService().recompute(db_session, contact)
        assert score > 70

    def test_reengagement_alert_depends_on_influence(self):
        svc = RelationshipHealthService()
        assert svc.reengagement_delay_days(0.8) == 30
        assert svc.reengagement_delay_days(0.5) == 60
        assert svc.reengagement_delay_days(0.1) == 90

    def test_stale_contact_is_flagged(self, db_session):
        contact = NetworkContact(organization="OldOrg", sector="transport", influence=0.9)
        db_session.add(contact)
        db_session.flush()
        db_session.add(
            Interaction(contact_id=contact.id, type="reunion", date=utcnow() - timedelta(days=120), sentiment="neutre")
        )
        db_session.flush()
        alerts = RelationshipHealthService().reengagement_alerts(db_session)
        assert any(a["contact_id"] == contact.id for a in alerts)


class TestBudgetGuard:
    @pytest.fixture(autouse=True)
    def clean_contingencies(self, db_session):
        db_session.query(ContingencyDraw).delete()
        db_session.query(Contingency).delete()
        db_session.flush()

    def test_consume_within_allocation(self, db_session):
        line = BudgetLine(pillar=1, allocated=1000, consumed=900, fiscal_year=2025)
        db_session.add(line)
        db_session.flush()
        result = BudgetGuardService().consume(db_session, line, 100)
        assert result["contingency_drawn"] == 0.0
        assert line.consumed == 1000

    def test_consume_beyond_allocation_requires_contingency(self, db_session):
        line = BudgetLine(pillar=2, allocated=1000, consumed=900, fiscal_year=2025)
        db_session.add(line)
        db_session.flush()
        with pytest.raises(AppError) as exc:
            BudgetGuardService().consume(db_session, line, 200)
        assert exc.value.code == "error.budget_exceeded"
        assert line.consumed == 900  # inchangé

    def test_consume_with_contingency_draws_provision(self, db_session):
        line = BudgetLine(pillar=3, allocated=1000, consumed=900, fiscal_year=2025)
        contingency = Contingency(risk_scenario="crise", provision=500)
        db_session.add_all([line, contingency])
        db_session.flush()
        result = BudgetGuardService().consume(db_session, line, 200)
        assert result["contingency_drawn"] == 100.0
        assert line.consumed == 1100
        assert contingency.drawn == 100.0

    def test_consume_beyond_remaining_reserve_fails(self, db_session):
        line = BudgetLine(pillar=4, allocated=1000, consumed=900, fiscal_year=2025)
        contingency = Contingency(risk_scenario="crise", provision=50)
        db_session.add_all([line, contingency])
        db_session.flush()
        with pytest.raises(AppError):
            BudgetGuardService().consume(db_session, line, 200)

    def test_contingency_cap_enforced(self, db_session):
        db_session.add(Contingency(risk_scenario="a", provision=90000))
        db_session.flush()
        with pytest.raises(AppError) as exc:
            BudgetGuardService().add_contingency(db_session, Contingency(risk_scenario="b", provision=20000))
        assert exc.value.code == "error.contingency_cap_reached"


class TestKpiEvaluation:
    def test_gap_creates_feedback_and_adjustment(self, db_session):
        kpi = KPI(type="satisfaction", value=50, target=100, period="2025-Q1", trend="down")
        db_session.add(kpi)
        db_session.flush()
        alert = KpiEvaluationService().evaluate(db_session, kpi)
        assert alert is not None
        from app.models import FeedbackItem, StrategyAdjustment

        fb = db_session.get(FeedbackItem, alert.feedback_item_id)
        assert fb.criticality == "high"
        adj = db_session.query(StrategyAdjustment).filter_by(feedback_item_id=fb.id).one()
        assert adj.trigger_type == "kpi_gap"
        assert fb.linked_adjustment_id == adj.id

    def test_small_gap_no_alert(self, db_session):
        kpi = KPI(type="adoption", value=99, target=100, period="2025-Q1")
        db_session.add(kpi)
        db_session.flush()
        assert KpiEvaluationService().evaluate(db_session, kpi) is None


class TestPilotLifecycle:
    def test_valid_transition(self, db_session):
        st = Stakeholder(name="S", role="CIO", organization="O", decision_level=4)
        sol = SectorSolution(sector="finance")
        db_session.add_all([st, sol])
        db_session.flush()
        pilot = PilotProgram(
            stakeholder_id=st.id,
            solution_id=sol.id,
            ethics_review_status="validated",
            privacy_impact_level="low",
            privacy_measures=["m"],
            fairness_status="done",
        )
        db_session.add(pilot)
        db_session.flush()
        PilotLifecycleService().transition(pilot, "running")
        assert pilot.status == "running"
        PilotLifecycleService().transition(pilot, "completed")
        assert pilot.status == "completed"

    def test_invalid_transition_rejected(self, db_session):
        st = Stakeholder(name="S2", role="CTO", organization="O2", decision_level=3)
        sol = SectorSolution(sector="sante")
        db_session.add_all([st, sol])
        db_session.flush()
        pilot = PilotProgram(stakeholder_id=st.id, solution_id=sol.id)
        db_session.add(pilot)
        db_session.flush()
        with pytest.raises(AppError) as exc:
            PilotLifecycleService().transition(pilot, "completed")
        assert exc.value.code == "error.invalid_transition"
