# Holistic Approach API

API backend de la démarche holistique d'entrée sur le marché de l'IA pour un laboratoire de recherche et innovation :
neuf piliers métier (veille concurrentielle, cartographie des décideurs, leadership d'opinion, personnalisation des
solutions, benchmarking & alliances, conseils consultatifs, réseau/CRM, boucle de retour, allocation budgétaire) plus un
socle transverse d'**IA responsable**.

- **Stack** : Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL (recommandé) ou SQLite (dev), PyJWT, structlog, pytest.
- **Architecture** : couches `api/` (routes) → `services/` (règles métier, dont les services partagés `app/services/shared.py`) → `repositories.py` → `models.py`.
- **Bilingue fr/en** : en-tête `Accept-Language` (défaut : `fr`).
- **Sécurité** : JWT (access + refresh), rôles `admin`, `strategist`, `contributor`, `reader` ; les PII des décideurs sont masquées pour le rôle `reader`.
- **Docs interactives** : `/docs` (Swagger) et `/redoc` ; spécification OpenAPI : `/openapi.json`.
- **IHM tableau de bord** : `/ui/` — SPA statique zéro-dépendance servie par l'API (login JWT, onglets Vue d'ensemble / Veille M1 / Stratégie M5-M6 / Réseau M7 / Budget M9 / IA responsable, bascule FR/EN).

## Démarrage en une commande (Docker)

```bash
docker compose up --build -d
docker compose exec app alembic upgrade head
docker compose exec app python -m app.seed
docker compose exec app python -m pytest -q   # optionnel : suite de tests
```

API sur http://localhost:8000 — docs sur http://localhost:8000/docs

## Démarrage local (sans Docker)

```bash
pip install -r requirements.txt
alembic upgrade head                 # migrations (DATABASE_URL par défaut : SQLite)
python -m app.seed                   # données d'amorçage
uvicorn app.main:app --reload        # http://localhost:8000
```

Pour PostgreSQL : `export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/holistic"` (voir `.env.example`).

## Comptes d'amorçage (mot de passe : `Password123!`)

| Rôle | Email |
|---|---|
| admin | admin@holistic.local |
| strategist | strategist@holistic.local |
| contributor | contributor@holistic.local |
| reader | reader@holistic.local |

## Exemples d'appels

```bash
# Authentification
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -d "username=admin@holistic.local" -d "password=Password123!" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
AUTH="Authorization: Bearer $TOKEN"

# Module 1 : créer un concurrent puis ingérer un signal (score + alerte + ajustement si seuil dépassé)
curl -s -X POST http://localhost:8000/competitors -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name":"NeuralCorp","sector":"IA","market_share":0.28,"offers":["LLM"],"segments":["grands comptes"],"initiatives":[]}'
curl -s -X POST http://localhost:8000/signals -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"competitor_id":1,"type":"investissement","source":"presse","date":"2026-01-10"}'
curl -s "http://localhost:8000/signals?min_relevance=70" -H "$AUTH"
curl -s http://localhost:8000/strategy-adjustments/1/trace -H "$AUTH"   # traçabilité jusqu'à la cause

# Module 4 : ROI + publication bloquée sans revue éthique validée
curl -s -X POST http://localhost:8000/roi/calculate -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"initial_cost":100000,"annual_cost":20000,"annual_gain":60000,"horizon_months":36}'
curl -s -X POST http://localhost:8000/sector-solutions/2/publish -H "$AUTH"   # 409 tant que ethics_status != validated

# Module 8 : un écart de KPI ferme la boucle vers un ajustement stratégique (module 5)
curl -s -X POST http://localhost:8000/kpis/1/evaluate -H "$AUTH"
curl -s "http://localhost:8000/kpis/dashboard?period=2025-Q1" -H "$AUTH"

# Module 9 : consommation au-delà de l'allocation = 409 sans contingence disponible
curl -s -X POST http://localhost:8000/budget-lines/1/consume -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"amount":90000,"justification":"campagne urgente"}'
curl -s "http://localhost:8000/budget/report?fiscal_year=2025" -H "$AUTH"

# Socle transverse + i18n
curl -s http://localhost:8000/responsible-ai/dashboard -H "$AUTH"
curl -s http://localhost:8000/competitors/999 -H "$AUTH" -H "Accept-Language: en"   # message en anglais
```

## Structure

```
app/
├── api/            # routeurs par module (schémas Pydantic + endpoints)
├── services/shared.py  # services partagés : SignalScoring, StrategyAdjustment, ROI, RelationshipHealth,
│                       # KpiEvaluation, BudgetGuard, ResponsibleAi, PilotLifecycle
├── models.py       # entités ORM (9 modules + socle transverse)
├── repositories.py # couche d'accès données (générique) + config
├── deps.py         # injection : get_db, get_current_user, require_role, get_locale
├── security.py     # JWT + hashage PBKDF2
├── i18n.py + locale/{fr,en}.json
├── main.py         # application, middlewares, /health, /ready
alembic/            # migrations versionnées
tests/              # tests unitaires (règles métier) + intégration (endpoints, i18n, RBAC)
```

## Tests

```bash
python -m pytest -q
```

41 tests : règles métier (score de pertinence, santé de relation, ROI, garde-fou budgétaire, transitions de pilote,
évaluation KPI) + endpoints (auth, CRUD, alertes, traçabilité inter-modules, gate éthique, consommation budgétaire)
+ bilinguisme et RBAC.

Voir `LIMITATIONS.md` (simplifications assumées) et `OPEN_QUESTIONS.md` (interprétations choisies).
