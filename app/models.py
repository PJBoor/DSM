from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base
from .security import utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="reader")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    lang_pref: Mapped[str] = mapped_column(String(5), default="fr")


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))


# ---------------- Module 1 : Market Insight ----------------

class Competitor(Base):
    __tablename__ = "competitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    sector: Mapped[str] = mapped_column(String(120))
    market_share: Mapped[float] = mapped_column(Float, default=0.0)
    offers: Mapped[list] = mapped_column(JSON, default=list)
    segments: Mapped[list] = mapped_column(JSON, default=list)
    initiatives: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class MarketSignal(Base):
    __tablename__ = "market_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(40), index=True)
    source: Mapped[str] = mapped_column(String(255))
    date: Mapped[date] = mapped_column(Date, index=True)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SignalAlert(Base):
    __tablename__ = "signal_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[int] = mapped_column(ForeignKey("market_signals.id", ondelete="CASCADE"), index=True)
    threshold: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CaseStudy(Base):
    __tablename__ = "case_studies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market: Mapped[str] = mapped_column(String(255), index=True)
    strategy: Mapped[str] = mapped_column(Text)
    results: Mapped[dict] = mapped_column(JSON, default=dict)
    lessons: Mapped[list] = mapped_column(JSON, default=list)
    reproducible_practices: Mapped[list] = mapped_column(JSON, default=list)
    failure_factors: Mapped[list] = mapped_column(JSON, default=list)
    keywords: Mapped[list] = mapped_column(JSON, default=list)


# ---------------- Module 2 : Decision Maker Mapping ----------------

class Stakeholder(Base):
    __tablename__ = "stakeholders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(120), index=True)
    organization: Mapped[str] = mapped_column(String(255))
    decision_level: Mapped[int] = mapped_column(Integer, default=1)
    budget_authority: Mapped[bool] = mapped_column(Boolean, default=False)
    influence_score: Mapped[float] = mapped_column(Float, default=0.0)
    engagement_level: Mapped[float] = mapped_column(Float, default=0.0)


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_type: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    motivations: Mapped[list] = mapped_column(JSON, default=list)
    pain_points: Mapped[list] = mapped_column(JSON, default=list)
    success_criteria: Mapped[list] = mapped_column(JSON, default=list)
    solution_preferences: Mapped[list] = mapped_column(JSON, default=list)


class CommunicationChannel(Base):
    __tablename__ = "communication_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stakeholder_id: Mapped[int] = mapped_column(ForeignKey("stakeholders.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    interaction_history: Mapped[list] = mapped_column(JSON, default=list)


class ContactPoint(Base):
    __tablename__ = "contact_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stakeholder_id: Mapped[int] = mapped_column(ForeignKey("stakeholders.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey("communication_channels.id", ondelete="SET NULL"), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    summary: Mapped[str] = mapped_column(Text, default="")


class StakeholderPersona(Base):
    __tablename__ = "stakeholder_personas"

    stakeholder_id: Mapped[int] = mapped_column(ForeignKey("stakeholders.id", ondelete="CASCADE"), primary_key=True)
    persona_id: Mapped[int] = mapped_column(ForeignKey("personas.id", ondelete="CASCADE"), primary_key=True)
    fit_score: Mapped[float] = mapped_column(Float, default=0.0)


# ---------------- Module 3 : Thought Leadership ----------------

class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(40), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    theme: Mapped[str] = mapped_column(String(255))
    reach_metrics: Mapped[dict] = mapped_column(JSON, default=dict)


class EventParticipation(Base):
    __tablename__ = "event_participations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event: Mapped[str] = mapped_column(String(255))
    format: Mapped[str] = mapped_column(String(40))
    date: Mapped[date] = mapped_column(Date)
    decision_makers_met: Mapped[list] = mapped_column(JSON, default=list)


class InfluencerRelationship(Base):
    __tablename__ = "influencer_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(40))
    organization: Mapped[str] = mapped_column(String(255))
    trust_level: Mapped[int] = mapped_column(Integer, default=3)
    exchange_history: Mapped[list] = mapped_column(JSON, default=list)


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(255))
    date: Mapped[date] = mapped_column(Date)


# ---------------- Module 4 : Solution Tailoring ----------------

class SectorSolution(Base):
    __tablename__ = "sector_solutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sector: Mapped[str] = mapped_column(String(60), index=True)
    use_cases: Mapped[list] = mapped_column(JSON, default=list)
    differentiators: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    ethics_status: Mapped[str] = mapped_column(String(20), default="pending")
    ethics_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    privacy_impact_level: Mapped[str] = mapped_column(String(20), default="unknown")
    privacy_measures: Mapped[list] = mapped_column(JSON, default=list)
    fairness_status: Mapped[str] = mapped_column(String(20), default="missing")


class ROICaseStudy(Base):
    __tablename__ = "roi_case_studies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sector: Mapped[str] = mapped_column(String(60), index=True)
    assumptions: Mapped[dict] = mapped_column(JSON, default=dict)
    gains: Mapped[dict] = mapped_column(JSON, default=dict)
    horizon_months: Mapped[int] = mapped_column(Integer, default=36)


class ROICalculation(Base):
    __tablename__ = "roi_calculations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_study_id: Mapped[int | None] = mapped_column(ForeignKey("roi_case_studies.id", ondelete="SET NULL"), nullable=True)
    inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    roi_percent: Mapped[float] = mapped_column(Float, default=0.0)
    payback_months: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20), default="unknown")
    risk_indicators: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PilotProgram(Base):
    __tablename__ = "pilot_programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stakeholder_id: Mapped[int] = mapped_column(ForeignKey("stakeholders.id", ondelete="CASCADE"), index=True)
    solution_id: Mapped[int] = mapped_column(ForeignKey("sector_solutions.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str] = mapped_column(Text, default="")
    milestones: Mapped[list] = mapped_column(JSON, default=list)
    measured_results: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="planned", index=True)
    ethics_review_status: Mapped[str] = mapped_column(String(20), default="pending")
    ethics_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    privacy_impact_level: Mapped[str] = mapped_column(String(20), default="unknown")
    privacy_measures: Mapped[list] = mapped_column(JSON, default=list)
    fairness_status: Mapped[str] = mapped_column(String(20), default="missing")


# ---------------- Module 5 : Benchmark & Alliances ----------------

class Collaboration(Base):
    __tablename__ = "collaborations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(60))
    partners: Mapped[list] = mapped_column(JSON, default=list)
    theme: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="active")


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    solution_evaluated: Mapped[str] = mapped_column(String(255))
    reference_competitors: Mapped[list] = mapped_column(JSON, default=list)
    differentiation_score: Mapped[float] = mapped_column(Float, default=0.0)
    gap_threshold: Mapped[float] = mapped_column(Float, default=10.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class BenchmarkAxisScore(Base):
    __tablename__ = "benchmark_axis_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("benchmark_runs.id", ondelete="CASCADE"), index=True)
    axis: Mapped[str] = mapped_column(String(60))
    our_score: Mapped[float] = mapped_column(Float, default=0.0)
    best_competitor_score: Mapped[float] = mapped_column(Float, default=0.0)
    gap: Mapped[float] = mapped_column(Float, default=0.0)


class StrategyAdjustment(Base):
    __tablename__ = "strategy_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trigger_type: Mapped[str] = mapped_column(String(40), index=True)
    trigger_detail: Mapped[str] = mapped_column(String(255), default="")
    signal_id: Mapped[int | None] = mapped_column(ForeignKey("market_signals.id", ondelete="SET NULL"), nullable=True)
    advisory_insight_id: Mapped[int | None] = mapped_column(ForeignKey("advisory_insights.id", ondelete="SET NULL"), nullable=True)
    feedback_item_id: Mapped[int | None] = mapped_column(ForeignKey("feedback_items.id", ondelete="SET NULL"), nullable=True)
    decision: Mapped[str] = mapped_column(Text)
    applied_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ---------------- Module 6 : Advisory Boards ----------------

class AdvisoryBoard(Base):
    __tablename__ = "advisory_boards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    theme: Mapped[str] = mapped_column(String(255))
    scope: Mapped[str] = mapped_column(String(120))


class Advisor(Base):
    __tablename__ = "advisors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile: Mapped[str] = mapped_column(String(255))
    expertise: Mapped[list] = mapped_column(JSON, default=list)
    networks: Mapped[list] = mapped_column(JSON, default=list)
    engagement: Mapped[str] = mapped_column(String(60), default="active")
    notability: Mapped[int] = mapped_column(Integer, default=3)


class BoardMembership(Base):
    __tablename__ = "board_memberships"

    board_id: Mapped[int] = mapped_column(ForeignKey("advisory_boards.id", ondelete="CASCADE"), primary_key=True)
    advisor_id: Mapped[int] = mapped_column(ForeignKey("advisors.id", ondelete="CASCADE"), primary_key=True)


class AdvisoryInsight(Base):
    __tablename__ = "advisory_insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advisor_id: Mapped[int] = mapped_column(ForeignKey("advisors.id", ondelete="CASCADE"), index=True)
    board_id: Mapped[int] = mapped_column(ForeignKey("advisory_boards.id", ondelete="CASCADE"), index=True)
    recommendation: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)


# ---------------- Module 7 : Network & CRM ----------------

class NetworkContact(Base):
    __tablename__ = "network_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str] = mapped_column(String(120), index=True)
    influence: Mapped[float] = mapped_column(Float, default=0.0)
    health_score: Mapped[float] = mapped_column(Float, default=0.0)


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("network_contacts.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(60))
    date: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    report: Mapped[str] = mapped_column(Text, default="")
    sentiment: Mapped[str] = mapped_column(String(20), default="neutre")


class Partnership(Base):
    __tablename__ = "partnerships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    partner: Mapped[str] = mapped_column(String(255))
    objective: Mapped[str] = mapped_column(Text, default="")
    co_developments: Mapped[list] = mapped_column(JSON, default=list)
    target_markets: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="active")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("network_contacts.id", ondelete="CASCADE"), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    stage: Mapped[str] = mapped_column(String(40), default="identified")
    value: Mapped[float] = mapped_column(Float, default=0.0)


# ---------------- Module 8 : Feedback Loop ----------------

class Survey(Base):
    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audience: Mapped[str] = mapped_column(String(60), index=True)
    questions: Mapped[list] = mapped_column(JSON, default=list)


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), index=True)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class FocusGroup(Base):
    __tablename__ = "focus_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participants: Mapped[list] = mapped_column(JSON, default=list)
    themes: Mapped[list] = mapped_column(JSON, default=list)
    synthesis: Mapped[str] = mapped_column(Text, default="")


class FeedbackItem(Base):
    __tablename__ = "feedback_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(60), index=True)
    verbatim: Mapped[str] = mapped_column(Text, default="")
    need: Mapped[str] = mapped_column(Text, default="")
    criticality: Mapped[str] = mapped_column(String(20), default="medium", index=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    linked_adjustment_id: Mapped[int | None] = mapped_column(
        ForeignKey("strategy_adjustments.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class KPI(Base):
    __tablename__ = "kpis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(60), index=True)
    value: Mapped[float] = mapped_column(Float, default=0.0)
    target: Mapped[float] = mapped_column(Float, default=0.0)
    period: Mapped[str] = mapped_column(String(20), index=True)
    trend: Mapped[str] = mapped_column(String(20), default="stable")


class KpiAlert(Base):
    __tablename__ = "kpi_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpis.id", ondelete="CASCADE"), index=True)
    deviation: Mapped[float] = mapped_column(Float, default=0.0)
    feedback_item_id: Mapped[int | None] = mapped_column(ForeignKey("feedback_items.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ---------------- Module 9 : Finance & Resources ----------------

class BudgetLine(Base):
    __tablename__ = "budget_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pillar: Mapped[int] = mapped_column(Integer, index=True)
    allocated: Mapped[float] = mapped_column(Float, default=0.0)
    consumed: Mapped[float] = mapped_column(Float, default=0.0)
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)


class ResourceAllocation(Base):
    __tablename__ = "resource_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    budget_line_id: Mapped[int] = mapped_column(ForeignKey("budget_lines.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(60))
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    attachment: Mapped[str] = mapped_column(String(255), default="")


class Contingency(Base):
    __tablename__ = "contingencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    risk_scenario: Mapped[str] = mapped_column(String(255))
    provision: Mapped[float] = mapped_column(Float, default=0.0)
    trigger_conditions: Mapped[list] = mapped_column(JSON, default=list)
    drawn: Mapped[float] = mapped_column(Float, default=0.0)


class ContingencyDraw(Base):
    __tablename__ = "contingency_draws"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    budget_line_id: Mapped[int] = mapped_column(ForeignKey("budget_lines.id", ondelete="CASCADE"), index=True)
    contingency_id: Mapped[int] = mapped_column(ForeignKey("contingencies.id", ondelete="CASCADE"), index=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    justification: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
