# OPEN_QUESTIONS

Interprétations choisies face aux ambiguïtés de la spécification (une phrase chacune).

1. **« Seuil configurable »** (pertinence des signaux, écart KPI, plafond de contingence) : stocké en base
   (`app_config`) et modifiable via endpoints dédiés, plutôt qu'en variable d'environnement, pour permettre un
   réglage à chaud par un administrateur.
2. **Rôle `reader` et PII des décideurs** : le lecteur voit les décideurs/contacts avec `name`/`organization`
   masqués (`***`), les autres rôles voient tout — « aucune donnée personnelle exposée sans autorisation » est
   interprété comme « sans le niveau de rôle suffisant ».
3. **Cycle de vie du pilote** : `planned → running → completed | failed | cancelled` (transitions contrôlées,
   toute autre transition renvoie 409).
4. **Calculateur de ROI** : entrées `initial_cost`, `annual_cost`, `annual_gain`, `horizon_months` ; ROI en %
   sur l'horizon, délai de retour en mois, risque `low|medium|high` (high si retour jamais atteint ou au-delà
   de l'horizon).
5. **Score de santé de relation** : fenêtre 180 jours, formule 40% fréquence / 30% récence / 30% sentiment,
   seuils de réengagement 30/60/90 jours selon l'influence (≥0.7 / ≥0.4 / sinon).
6. **Score de pertinence d'un signal** : 50% récence (décroissance sur 365 j) + 30% type (investissement 1.0,
   lancement 0.9, partenariat 0.7, campagne 0.5) + 20% part de marché du concurrent émetteur.
7. **Liaison module 8 → module 5** : l'évaluation d'un KPI en écart crée un `FeedbackItem` priorisé *et* un
   `StrategyAdjustment` (`trigger_type=kpi_gap`) qui le référence, la boucle étant consultable via
   `/strategy-adjustments/{id}/trace`.
8. **« Bloquer la publication »** : `POST /sector-solutions/{id}/publish` renvoie 409 tant que
   `ethics_status != "validated"` ; les champs éthiques des pilotes sont obligatoires à la création (validation
   Pydantic).
