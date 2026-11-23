# LIMITATIONS

Simplifications volontairement assumées, avec la raison et le chemin d'achèvement.

1. **Base de données par défaut en SQLite** (`DATABASE_URL` non défini). Raison : démarrage en une commande sans
   service externe. Chemin vers la production : `DATABASE_URL=postgresql+psycopg://...` (fourni via `docker-compose.yml`
   et `.env.example`) ; le schéma et les migrations Alembic sont SGBD-agnostiques (types génériques SQLAlchemy).
2. **Jetons de rafraîchissement stateless (JWT)** sans liste de révocation en base. Raison : simplicité. Chemin :
   table `revoked_tokens` + vérification dans `deps.get_current_user`.
3. **Masquage des PII limité aux ressources `stakeholders` et `network-contacts` pour le rôle `reader`**.
   Raison : périmètre démonstrateur. Chemin : appliquer le même filtre à toute ressource contenant des données
   personnelles (interactions, opportunités, participants d'enquêtes).
4. **Pas de limitation de débit (rate limiting)** ni de TLS dans l'app (terminaison TLS déléguée au reverse proxy
   Docker). Chemin : middleware `slowapi` + déploiement derrière un proxy TLS.
5. **Formules de scoring documentées et paramétrables uniquement via les seuils en config** (`signal_alert_threshold`,
   `kpi_deviation_threshold`, `contingency_cap`) ; les pondérations internes (50/30/20 etc.) sont des constantes
   explicites dans `app/services/shared.py`. Chemin : table de pondérations configurables si besoin métier.
6. **Index de leadership d'opinion et tableau de crédibilité** : normalisations par plafonds fixes (documentés dans
   le code). Chemin : remplacer par des percentiles calculés sur l'historique complet.
7. **Pagination simple `skip`/`limit`** (pas de curseur). Chemin : pagination par curseur pour les gros volumes de signaux.
8. **Journalisation vers la sortie standard** (JSON structlog). Chemin : shipper vers un agrégateur (ELK/Loki) en prod.
