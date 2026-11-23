"""Données d'amorçage réalistes couvrant les neuf modules et le socle transverse.

Usage : python -m app.seed
"""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .models import (
    AdvisoryBoard,
    AdvisoryInsight,
    Advisor,
    BenchmarkAxisScore,
    BenchmarkRun,
    BudgetLine,
    CaseStudy,
    Citation,
    CommunicationChannel,
    Competitor,
    ContactPoint,
    Contingency,
    EventParticipation,
    FeedbackItem,
    FocusGroup,
    InfluencerRelationship,
    Interaction,
    KPI,
    MarketSignal,
    NetworkContact,
    Opportunity,
    Partnership,
    Persona,
    PilotProgram,
    Publication,
    ROICaseStudy,
    ResourceAllocation,
    SectorSolution,
    Stakeholder,
    StakeholderPersona,
    StrategyAdjustment,
    Survey,
    SurveyResponse,
    User,
)
from .security import hash_password, utcnow
from .services.shared import (
    KpiEvaluationService,
    RelationshipHealthService,
    SignalScoringService,
    StrategyAdjustmentService,
)

SEED_PASSWORD = "Password123!"


def seed(db: Session) -> None:
    if db.execute(select(User)).first():
        print("Base déjà amorcée, rien à faire.")
        return

    users = [
        User(email="admin@holistic.local", hashed_password=hash_password(SEED_PASSWORD), role="admin"),
        User(email="strategist@holistic.local", hashed_password=hash_password(SEED_PASSWORD), role="strategist"),
        User(email="contributor@holistic.local", hashed_password=hash_password(SEED_PASSWORD), role="contributor"),
        User(email="reader@holistic.local", hashed_password=hash_password(SEED_PASSWORD), role="reader"),
    ]
    db.add_all(users)

    # Module 1 : 3 concurrents, signaux, étude de cas
    competitors = [
        Competitor(name="NeuralCorp", sector="IA générique", market_share=0.28,
                   offers=["LLM entreprise", "Agents autonomes"], segments=["Grands comptes"],
                   initiatives=["Levée de fonds série C"]),
        Competitor(name="DataMind AI", sector="MLOps", market_share=0.15,
                   offers=["Plateforme MLOps"], segments=["PME", "ETI"], initiatives=["Partenariat cloud"]),
        Competitor(name="VisionWorks", sector="Vision par ordinateur", market_share=0.09,
                   offers=["Détection d'anomalies industrielles"], segments=["Manufacture"], initiatives=[]),
    ]
    db.add_all(competitors)
    db.flush()

    today = date.today()
    signals = [
        MarketSignal(competitor_id=competitors[0].id, type="investissement", source="Communiqué de presse", date=today - timedelta(days=5)),
        MarketSignal(competitor_id=competitors[0].id, type="lancement", source="Blog produit", date=today - timedelta(days=40)),
        MarketSignal(competitor_id=competitors[1].id, type="partenariat", source="Presse spécialisée", date=today - timedelta(days=120)),
    ]
    db.add_all(signals)
    db.flush()
    scoring = SignalScoringService()
    for s in signals:
        scoring.evaluate(db, s)

    db.add(CaseStudy(
        market="Finance - scoring crédit",
        strategy="Déploiement d'un modèle de scoring explicable avec boucle de validation réglementaire.",
        results={"precision": "+12%", "delai_decision": "-60%"},
        lessons=["Impliquer le conformité dès le cadrage"],
        reproducible_practices=["Data product canvas", "Revues éthiques mensuelles"],
        failure_factors=["Sous-estimer la qualité des données historiques"],
        keywords=["finance", "reglementation", "explicabilite"],
    ))

    # Module 2 : 8 décideurs, 2 personas, canaux, points de contact
    stakeholders = [
        Stakeholder(name="Alice Martin", role="CIO", organization="Banque Hexa", decision_level=5, budget_authority=True),
        Stakeholder(name="Bruno Keller", role="CTO", organization="Banque Hexa", decision_level=4, budget_authority=False),
        Stakeholder(name="Chloé Dubois", role="CEO", organization="LogiTrans", decision_level=5, budget_authority=True),
        Stakeholder(name="David Nguyen", role="CIO", organization="Hopital Nord", decision_level=4, budget_authority=True),
        Stakeholder(name="Emma Rossi", role="CTO", organization="Industria", decision_level=4, budget_authority=False),
        Stakeholder(name="Fabien Leroy", role="Directeur Innovation", organization="AssurAlpha", decision_level=3, budget_authority=True),
        Stakeholder(name="Garance Petit", role="CIO", organization="RetailPlus", decision_level=3, budget_authority=False),
        Stakeholder(name="Hugo Fontaine", role="CEO", organization="AgriSense", decision_level=5, budget_authority=True),
    ]
    db.add_all(stakeholders)
    db.flush()

    personas = [
        Persona(role_type="CIO bancaire", motivations=["Réduire le risque opérationnel"], pain_points=["Conformité réglementaire"],
                success_criteria=["Audit réussi", "ROI en 18 mois"], solution_preferences=["Explicabilité", "Hébergement souverain"]),
        Persona(role_type="CTO industriel", motivations=["Automatiser la production"], pain_points=["Dette technique"],
                success_criteria=["Disponibilité 99.9%"], solution_preferences=["Edge computing", "Faible latence"]),
    ]
    db.add_all(personas)
    db.flush()
    db.add_all([
        StakeholderPersona(stakeholder_id=stakeholders[0].id, persona_id=personas[0].id, fit_score=95.0),
        StakeholderPersona(stakeholder_id=stakeholders[4].id, persona_id=personas[1].id, fit_score=88.0),
    ])
    ch = CommunicationChannel(stakeholder_id=stakeholders[0].id, type="linkedin", interaction_history=["Échange initial"])
    db.add(ch)
    db.flush()
    db.add_all([
        ContactPoint(stakeholder_id=stakeholders[0].id, channel_id=ch.id, at=utcnow() - timedelta(days=10), summary="Keynote IA responsable"),
        ContactPoint(stakeholder_id=stakeholders[0].id, channel_id=ch.id, at=utcnow() - timedelta(days=45), summary="Webinar conformité"),
        ContactPoint(stakeholder_id=stakeholders[2].id, at=utcnow() - timedelta(days=200), summary="Salon Supply Chain (relation froide)"),
    ])

    # Module 3
    pub = Publication(type="livre_blanc", date=today - timedelta(days=30), theme="IA responsable en entreprise", reach_metrics={"telechargements": 1200})
    db.add(pub)
    db.flush()
    db.add(Citation(publication_id=pub.id, source="Rapport analyste Gartner-like", date=today - timedelta(days=10)))
    db.add(EventParticipation(event="AI Summit Paris", format="keynote", date=today - timedelta(days=15), decision_makers_met=["Alice Martin", "Chloé Dubois"]))
    db.add(InfluencerRelationship(kind="analyste", organization="Cabinet d'analystes indépendants", trust_level=4, exchange_history=["Briefing trimestriel"]))

    # Module 4 : solutions sectorielles, étude ROI, pilote
    sol_fin = SectorSolution(sector="finance", use_cases=["Scoring crédit", "Détection de fraude"], differentiators=["Explicabilité certifiée"],
                             status="draft", ethics_status="validated", ethics_review_date=today - timedelta(days=60),
                             privacy_impact_level="high", privacy_measures=["Pseudonymisation", "DPO désigné"], fairness_status="done")
    sol_sante = SectorSolution(sector="sante", use_cases=["Aide au diagnostic"], differentiators=["Conformité HIPAA-like"],
                               status="draft", ethics_status="pending", privacy_impact_level="high", privacy_measures=[], fairness_status="missing")
    db.add_all([sol_fin, sol_sante])
    db.flush()
    db.add(ROICaseStudy(sector="finance", assumptions={"cout_initial": 150000}, gains={"economie_an": 80000, "performance": "+12%"}, horizon_months=36))
    db.add(PilotProgram(
        stakeholder_id=stakeholders[0].id, solution_id=sol_fin.id, scope="Pilote scoring crédit sur 3 mois",
        milestones=["Cadrage", "Déploiement sandbox", "Revue éthique"], measured_results={},
        status="running", ethics_review_status="validated", ethics_review_date=today - timedelta(days=60),
        privacy_impact_level="high", privacy_measures=["Pseudonymisation"], fairness_status="done",
    ))

    # Module 5 : benchmark (l'ajustement lié au signal a déjà été créé par SignalScoringService)
    run = BenchmarkRun(solution_evaluated="Plateforme MLOps interne", reference_competitors=["DataMind AI"], gap_threshold=10.0)
    db.add(run)
    db.flush()
    db.add_all([
        BenchmarkAxisScore(run_id=run.id, axis="fonctionnalites", our_score=70, best_competitor_score=85, gap=-15.0),
        BenchmarkAxisScore(run_id=run.id, axis="performance", our_score=80, best_competitor_score=78, gap=2.0),
        BenchmarkAxisScore(run_id=run.id, axis="satisfaction", our_score=75, best_competitor_score=82, gap=-7.0),
    ])

    # Module 6
    board = AdvisoryBoard(theme="Éthique et conformité IA", scope="produit")
    db.add(board)
    db.flush()
    adv = Advisor(profile="Professeure d'éthique numérique", expertise=["Éthique IA", "Droit"], networks=["Comités réglementaires"], notability=5)
    db.add(adv)
    db.flush()
    insight = AdvisoryInsight(advisor_id=adv.id, board_id=board.id, recommendation="Certifier les revues éthiques avant toute publication", domain="gouvernance", status="open")
    db.add(insight)

    # Module 7
    contact = NetworkContact(organization="Banque Hexa", sector="finance", influence=0.85)
    db.add(contact)
    db.flush()
    db.add_all([
        Interaction(contact_id=contact.id, type="reunion", date=utcnow() - timedelta(days=12), report="Bonne dynamique", sentiment="positif"),
        Interaction(contact_id=contact.id, type="evenement", date=utcnow() - timedelta(days=60), report="Stand visité", sentiment="neutre"),
    ])
    RelationshipHealthService().recompute(db, contact)
    cold = NetworkContact(organization="AgriSense", sector="agriculture", influence=0.8)
    db.add(cold)
    db.flush()
    db.add(Interaction(contact_id=cold.id, type="reunion", date=utcnow() - timedelta(days=200), report="Dernier échange", sentiment="neutre"))
    RelationshipHealthService().recompute(db, cold)
    db.add(Partnership(partner="CloudSouverain SA", objective="Hébergement des pilotes", co_developments=["Connecteur API"], target_markets=["France", "Belgique"], status="active"))
    db.add(Opportunity(contact_id=contact.id, description="Contrat pilote scoring crédit", stage="negotiation", value=250000.0))

    # Module 8
    survey = Survey(audience="decideurs", questions=["Notez votre satisfaction globale (1-5)", "Quels besoins insatisfaits ?"])
    db.add(survey)
    db.flush()
    db.add(SurveyResponse(survey_id=survey.id, answers={"satisfaction": 4, "besoins": "Tarifs transparents"}))
    db.add(FocusGroup(participants=["Alice Martin", "Chloé Dubois"], themes=["Adoption IA"], synthesis="Forte attente d'explicabilité."))
    kpi = KPI(type="satisfaction", value=62.0, target=80.0, period="2025-Q1", trend="down")
    db.add(kpi)
    db.flush()
    KpiEvaluationService().evaluate(db, kpi)
    db.add(FeedbackItem(source="enquete", verbatim="Les tarifs manquent de lisibilité", need="Grille tarifaire publique", criticality="medium", status="open"))

    # Module 9 : budgets par exercice pour les 8 piliers + contingence
    for pillar in range(1, 9):
        db.add(BudgetLine(pillar=pillar, allocated=50000.0 if pillar != 1 else 80000.0, consumed=12000.0, fiscal_year=2025))
    db.add(BudgetLine(pillar=1, allocated=60000.0, consumed=5000.0, fiscal_year=2026))
    db.flush()
    line1 = db.execute(select(BudgetLine).where(BudgetLine.pillar == 1, BudgetLine.fiscal_year == 2025)).scalar_one()
    db.add(ResourceAllocation(budget_line_id=line1.id, type="outil_intelligence", cost=8000.0, attachment="Abonnement veille concurrentielle"))
    db.add(Contingency(risk_scenario="Lancement surprise d'un concurrent majeur", provision=30000.0, trigger_conditions=["Signal investissement pertinence >= 70"]))

    db.commit()
    print("Amorçage terminé : 4 utilisateurs (mot de passe : Password123!), 3 concurrents, 8 décideurs, 1 pilote, 1 benchmark, 1 enquête, budgets 2025/2026.")


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)


if __name__ == "__main__":
    main()
