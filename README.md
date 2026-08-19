# Agent IA "Data Analyst" — Hybride (Bedrock + infra on-premise)

Agent conversationnel qui répond à des questions métier sur des données
d'entreprise (SQL, calcul, visualisation, rapports), avec génération LLM sur
AWS Bedrock et tout le reste (bases, exécution de code, stockage,
observabilité) hébergé en local via Docker Compose.

## Objectif

Permettre à un utilisateur non technique de poser une question en langage
naturel sur des données d'entreprise réparties sur plusieurs sources
(ERP/CRM, export e-commerce, avis clients, taux de change) et d'obtenir une
réponse fiable — chiffrée, visualisée ou exportée — sans jamais laisser le
LLM produire un chiffre par lui-même.

**Principe non négociable : le LLM ne calcule jamais de chiffre lui-même.**
Il génère du SQL/Python, exécuté de façon déterministe en local ; les
résultats reviennent au LLM pour interprétation uniquement.

## Fonctionnement

Un agent LangGraph reçoit la question de l'utilisateur (via Chainlit) et
décide seul, via l'API Bedrock Converse (`toolConfig`), quel(s) outil(s)
invoquer :

- **Interroger les données** : génère du SQL (RAG sur le schéma via Qdrant),
  le valide (SELECT uniquement, garde-fous anti-injection), l'exécute en
  lecture seule sur Postgres
- **Calculer** : génère du Python exécuté dans un sandbox Docker isolé
  (aucun réseau, non-root, quotas), pour tout calcul au-delà du SQL
- **Visualiser** : génère un graphique Plotly dans le sandbox, puis relit
  l'image produite (Bedrock vision) pour la commenter
- **Fédérer** : croise Postgres et des fichiers Parquet dans une même
  requête DuckDB, avec résolution d'entités et conversion de devise
- **Exporter** : produit Excel/CSV/PDF et les dépose sur MinIO (URLs
  pré-signées, expirantes)
- **Rapporter** : génère un rapport narratif où chaque affirmation chiffrée
  référence une ligne vérifiable des données, avec annexe de traçabilité
  complète (SQL, coût, identité, hash du journal d'audit)

L'agent enchaîne les outils au fil de la conversation (ex : "trace un
graphique" après une question SQL, sans redemander les données), jusqu'à
répondre en langage naturel. Chaque appel Bedrock est tracé dans Langfuse
(coût, tokens) et chaque action (SQL exécuté, code Python, requête rejetée)
est journalisée dans un journal d'audit immuable (chaîne de hash).

## Architecture

AWS Bedrock (Claude, Titan Embeddings) pour toute génération LLM ; le reste
tourne en local :

| Composant | Rôle |
|---|---|
| AWS Bedrock — Claude (Converse API) | Génération SQL/Python/rapports, vision |
| AWS Bedrock — Titan Embeddings v2 | Embeddings pour le RAG schéma |
| PostgreSQL | Northwind (ERP/CRM) |
| Parquet | Online Retail II (e-commerce), avis clients (Kaggle) |
| Frankfurter | API taux de change |
| Qdrant | Base vectorielle (recherche hybride sur le schéma) |
| SQLGlot / SQLFluff / rank-bm25 | Validation SQL, recherche hybride |
| Sandbox Docker isolé | Exécution du code Python généré |
| pandas / numpy / scipy / statsmodels / scikit-learn / polars | Analyse |
| Plotly + Kaleido | Graphiques (PNG + interactif) |
| DuckDB | Moteur analytique cross-source |
| XlsxWriter / WeasyPrint | Export Excel, PDF |
| MinIO | Stockage d'artefacts (S3-compatible) |
| Redis / ClickHouse | Tâches asynchrones, socle observabilité |
| Langfuse | Traçage des appels LLM, coût |
| LangGraph | Orchestration agentique (agent à outils) |
| Chainlit | Interface de chat |

## Structure du projet

```
config/settings.py     Configuration centralisée
src/agent/
  llm/                  Clients Bedrock (Claude, Titan Embeddings)
  db/, ingestion/       Postgres, chargement des sources
  schema/, sql/         RAG schéma (Qdrant), Text-to-SQL, validation, exécution
  sandbox/, python_exec/ Exécution Python isolée
  viz/                  Graphiques Plotly + relecture vision
  export/               Excel/CSV/PDF + upload MinIO
  federation/           DuckDB cross-source, résolution d'entités, devises
  report/               Rapports narratifs traçables
  feedback/, audit/     Feedback utilisateur, journal d'audit (hash-chaîné)
  evaluation/           Exactitude d'exécution, robustesse, coût
  observability/        Langfuse, tarification Bedrock
  orchestrator/         Agent LangGraph (outils, état de session, graphe)
app/chainlit_app.py    Interface de chat
sandbox/               Image Docker d'exécution isolée
infra/                 Init Postgres, buckets MinIO
data/                  raw/processed/logs/artifacts (gitignored)
evaluation/            Questions de validation + eval_dataset.json
scripts/               Scripts d'exécution manuelle (appels Bedrock réels)
tests/unit/            Tests unitaires (Bedrock mocké)
```

## Sécurité

- Aucune credential en dur (profil AWS local / variables d'environnement)
- SQL généré : SELECT uniquement, tables/colonnes vérifiées contre le schéma
  réel, LIMIT forcé, exécuté via un rôle Postgres `agent_readonly` sans
  écriture — toute requête rejetée est journalisée
- Code Python exécuté uniquement dans un sandbox isolé (`--network none`,
  FS lecture seule, non-root, quotas CPU/RAM/PID, timeout dur)
- Résistance à l'injection SQL vérifiée par une batterie de charges
  malveillantes passées directement au validateur
- Journal d'audit immuable (chaîne de hash) : `verify_journal()` détecte
  toute altération rétroactive
- URLs de fichiers exportés pré-signées et expirantes (24h), jamais de
  bucket public
- Coût Bedrock jamais inventé : `None` si le modèle est absent de la table
  de tarification, plutôt qu'un chiffre approximatif
