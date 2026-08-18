# Agent IA "Data Analyst" — Hybride (Bedrock + infra on-premise)

Agent conversationnel capable de répondre à des questions métier sur des
données d'entreprise (SQL, calcul, visualisation, rapports), avec génération
LLM déportée sur AWS Bedrock et tout le reste (bases, exécution de code,
stockage, observabilité) hébergé en local via Docker Compose.

Principe non négociable : **le LLM ne calcule jamais de chiffre lui-même**.
Il génère du SQL/Python, exécuté de façon déterministe en local ; les
résultats reviennent au LLM pour interprétation uniquement.

Ce dépôt est construit incrément par incrément. Statut actuel : **Phase 7 —
Évaluation (dernière phase du plan initial)**, sur la base de la Phase 6
(rapports, traçabilité, feedback), de la Phase 5 (analyse multi-sources), de
la Phase 4 (génération de fichiers), de la Phase 3 (visualisation avec
relecture vision), de la Phase 2 (sandbox d'exécution Python), de la Phase 1
(Text-to-SQL avec garde-fous) et de la Phase 0 (socle infra + ingestion des
4 sources de données). Les 7 phases prévues sont complètes.

> **Identité (Phase 6)** : le stack technique original prévoit Keycloak pour
> l'authentification, mais aucune phase de ce projet ne le déploie (pas dans
> `docker-compose.yml`) - décision prise avec l'utilisateur pour rester dans
> le périmètre restant (Phase 7). La traçabilité "identité" du journal
> d'audit utilise un identifiant léger (`AGENT_USER_IDENTITY` ou utilisateur
> du système), pas un SSO complet. À revoir si le projet est mis en
> production avec plusieurs utilisateurs réels.

> À partir de la Phase 1, tout ce qui appelle Bedrock (génération SQL,
> indexation du schéma) est écrit et testé (avec des clients Bedrock
> simulés), mais n'est **pas exécuté en conditions réelles par l'agent de
> build** — c'est délibéré : l'utilisateur exécute lui-même ces commandes
> pour garder le contrôle des appels/coûts Bedrock. Les sections ci-dessous
> l'indiquent explicitement à chaque fois.

## Prérequis

- Docker + Docker Compose (v2, plugin `docker compose`)
- Python 3.12+ et [`uv`](https://docs.astral.sh/uv/)
- Un compte AWS avec accès activé à Bedrock pour au moins un modèle Claude
  (Converse API) et `amazon.titan-embed-text-v2:0`, dans une région où ces
  modèles sont disponibles (ex: `us-west-2`)
- Un profil AWS configuré en local (`~/.aws/credentials` / `~/.aws/config`),
  ou des variables d'environnement `AWS_ACCESS_KEY_ID` /
  `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN`
- (Optionnel, pour l'ingestion des avis clients) un compte Kaggle avec un
  token API : https://www.kaggle.com/settings → "Create New Token"

## Démarrage

### 1. Configuration

```bash
cp .env.example .env
```

Éditez `.env` :

- `AWS_REGION` / `AWS_PROFILE` : votre configuration AWS
- `BEDROCK_MODEL_ID` : ID d'inference profile Bedrock pour Claude. Vérifiez
  les modèles auxquels votre compte a accès avec :
  ```bash
  aws bedrock list-inference-profiles --region <votre_région> \
    --query "inferenceProfileSummaries[?contains(inferenceProfileId, 'claude')].inferenceProfileId"
  ```
  Le défaut (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`) fonctionne sur
  la plupart des comptes ; `claude-sonnet-5` n'est pas encore activé
  partout.
- Tous les mots de passe locaux (`POSTGRES_*`, `MINIO_*`, `LANGFUSE_*`,
  `CLICKHOUSE_PASSWORD`) : générez des valeurs aléatoires, par exemple
  ```bash
  python3 -c "import secrets; print(secrets.token_hex(16))"
  ```
- Les secrets Langfuse (`LANGFUSE_SALT`, `LANGFUSE_ENCRYPTION_KEY`,
  `LANGFUSE_NEXTAUTH_SECRET`) : `openssl rand -hex 32`
- Les clés API Langfuse (`LANGFUSE_INIT_PROJECT_PUBLIC_KEY` /
  `_SECRET_KEY`, à recopier aussi dans `LANGFUSE_PUBLIC_KEY` /
  `LANGFUSE_SECRET_KEY`) : ces valeurs bootstrapent automatiquement
  l'organisation, le projet et l'utilisateur admin Langfuse au premier
  démarrage — pas d'inscription manuelle nécessaire. Générez-les avec :
  ```bash
  python3 -c "import secrets; print('pk-lf-'+secrets.token_hex(16)); print('sk-lf-'+secrets.token_hex(16))"
  ```

### 2. Infrastructure locale

```bash
docker compose up -d
```

Démarre : Postgres (bases `northwind` + `langfuse`, rôles `agent_app` /
`agent_readonly` créés automatiquement), Qdrant, MinIO (buckets `artifacts` /
`langfuse` créés automatiquement), Redis, ClickHouse, et Langfuse
(web + worker). Premier démarrage : compter ~1 minute pour que tous les
services deviennent sains.

L'UI Langfuse est accessible sur http://localhost:3001 (identifiants :
`LANGFUSE_INIT_USER_EMAIL` / `LANGFUSE_INIT_USER_PASSWORD`).

### 3. Dépendances Python

```bash
uv sync
```

### 4. Ingestion des données

```bash
export PYTHONPATH="src:."

uv run python -m agent.ingestion.load_northwind      # Postgres: schéma + données Northwind
uv run python -m agent.ingestion.load_online_retail   # Parquet: Online Retail II, anomalies loguées
uv run python -m agent.ingestion.check_frankfurter    # Vérifie l'accès à l'API taux de change
uv run python -m agent.ingestion.load_reviews         # Parquet: échantillon d'avis Amazon (nécessite Kaggle)
```

`load_reviews.py` nécessite des identifiants Kaggle (`KAGGLE_USERNAME` +
`KAGGLE_KEY` en variables d'environnement, ou `~/.kaggle/kaggle.json`). Sans
eux, le script échoue avec un message explicite plutôt que silencieusement.

### 5. Vérification de santé

```bash
uv run python -m agent.health.healthcheck
```

Vérifie Postgres, Qdrant, MinIO, Redis, Langfuse, et effectue un appel
Bedrock réel (Claude + Titan Embeddings). Sortie tabulaire, code de sortie
non-zéro si un service échoue.

### 6. Sandbox Python (Phase 2)

```bash
docker build -t hybrid-data-analyst-sandbox:latest sandbox/
```

Construit l'image d'exécution isolée (pandas, numpy, scipy, statsmodels,
scikit-learn, polars, plotly + Chrome headless pour l'export PNG des
graphiques). Requise avant de lancer les tests ou les pipelines Python/viz
(`uv run pytest` ignore automatiquement les tests du sandbox si l'image ou
Docker sont absents). Le build télécharge Chrome (~13s de plus) : la
compilation de l'image nécessite un accès réseau, contrairement à son
exécution (`--network none`, voir section Sécurité).

### 7. Tests

```bash
uv run pytest       # tests unitaires (mocks pour Bedrock ; Postgres/Qdrant/Docker réels et locaux)
uv run ruff check .
uv run mypy src config
```

### 8. Text-to-SQL (Phase 1) — à exécuter vous-même

Ces deux commandes appellent réellement Bedrock (Titan Embeddings puis
Claude) :

```bash
export PYTHONPATH="src:."

# Une seule fois : indexe le schéma Northwind dans Qdrant (Titan Embeddings)
uv run python -m agent.schema.indexer

# Une question :
uv run python -m agent.sql.cli "Combien de clients y a-t-il au total ?"

# Les 20 questions de validation (evaluation/phase1_questions_northwind.md) :
uv run python scripts/run_phase1_questions.py
```

Chaque réponse affiche le SQL généré (y compris les tentatives rejetées et
corrigées automatiquement), le SQL final réellement exécuté, et les lignes
retournées. Le journal `data/logs/sql_audit.jsonl` trace toute tentative
(acceptée, rejetée, ou en erreur d'exécution).

### 9. Calcul au-delà du SQL (Phase 2) — à exécuter vous-même

Combine le pipeline Text-to-SQL (Phase 1) et une analyse Python exécutée
dans le sandbox isolé. Appelle réellement Bedrock deux fois (génération SQL
puis génération Python) :

```bash
export PYTHONPATH="src:."

uv run python -m agent.python_exec.cli \
  "Donne-moi la quantité et le prix unitaire de chaque ligne de commande" \
  "Calcule la corrélation entre le prix unitaire et la quantité commandée"

# Les 10 questions de validation (evaluation/phase2_questions_northwind.md) :
uv run python scripts/run_phase2_questions.py
```

Chaque réponse affiche le code Python généré (tentatives + corrections), le
code final exécuté dans le sandbox, et le résultat (DataFrame ou valeur).
Le journal `data/logs/python_audit.jsonl` trace tout code exécuté.

### 10. Graphique + relecture vision (Phase 3) — à exécuter vous-même

Combine le pipeline Text-to-SQL (Phase 1) et la génération d'un graphique
Plotly dans le sandbox isolé, puis demande à Claude (Bedrock, vision) de
commenter l'image PNG réellement produite. Appelle réellement Bedrock trois
fois (génération SQL, génération du graphique, vision) :

```bash
export PYTHONPATH="src:."

uv run python -m agent.viz.cli \
  "Donne-moi le chiffre d'affaires total par catégorie de produits" \
  "Trace un graphique en barres du chiffre d'affaires par catégorie"

# Les 8 questions de validation (evaluation/phase3_questions_northwind.md) :
uv run python scripts/run_phase3_questions.py
```

Chaque réponse affiche le code du graphique généré (tentatives +
corrections), le chemin du PNG et de la version HTML interactive
(`data/artifacts/charts/`), et le commentaire vision ancré sur l'image.

### 11. Fichiers téléchargeables (Phase 4) — à exécuter vous-même

Récupère les données via le pipeline Text-to-SQL (Phase 1), génère Excel
(multi-onglets, graphique natif), CSV et PDF (tableau + graphique intégré),
puis les téléverse sur MinIO avec des URLs pré-signées (24h). Appelle
réellement Bedrock une fois (génération SQL) ; la génération des fichiers et
l'upload MinIO sont entièrement déterministes :

```bash
export PYTHONPATH="src:."

uv run python -m agent.export.cli \
  "Donne-moi le chiffre d'affaires total par catégorie de produits"

# Formats spécifiques, sans upload (fichiers gardés en local) :
uv run python -m agent.export.cli "..." --formats csv pdf --no-upload
```

Affiche une URL pré-signée par format généré (ou le chemin local avec
`--no-upload`). Les fichiers sont ouvrables directement (testé : Excel avec
openpyxl, PDF avec `%PDF-` + extraction de texte, CSV round-trip pandas).

### 12. Analyse multi-sources (Phase 5) — à exécuter vous-même

Fédère Northwind (Postgres) et Online Retail II (Parquet) dans une même
connexion DuckDB, avec résolution d'entités (noms de pays normalisés entre
les deux sources : "UK" ↔ "United Kingdom", "EIRE" ↔ "Ireland"...) et
conversion de devise en direct (Online Retail II est en GBP, taux Frankfurter
injecté dans le prompt). Appelle réellement Bedrock (génération SQL fédérée,
dialecte DuckDB) :

```bash
export PYTHONPATH="src:."

uv run python -m agent.federation.cli \
  "Compare le nombre de commandes Northwind au nombre de lignes Online Retail II pour le Royaume-Uni et la France"

# Avec synthèse qualitative des avis clients (si l'ingestion Kaggle a été faite) :
uv run python -m agent.federation.cli "..." --with-reviews

# Les 8 questions de validation (evaluation/phase5_questions_federation.md) :
uv run python scripts/run_phase5_questions.py
```

Chaque réponse affiche le SQL fédéré généré (tentatives + corrections), le
SQL final réellement exécuté sur les deux sources, et les lignes retournées.

### 13. Rapport traçable (Phase 6) — à exécuter vous-même

Question -> SQL (Phase 1) -> rapport narratif où chaque affirmation
chiffrée référence une ligne vérifiable du tableau de données (Bedrock) ->
PDF avec annexe de traçabilité complète (SQL exécuté, tableau, identité,
modèle, tokens, coût, hash du journal d'audit immuable) -> upload MinIO ->
trace Langfuse avec coût. Appelle réellement Bedrock deux fois (génération
SQL + génération narrative) :

```bash
export PYTHONPATH="src:."

uv run python -m agent.report.cli \
  "Quel est le chiffre d'affaires total par catégorie de produits ?"

# Les 6 questions de validation (evaluation/phase6_questions_report.md) :
uv run python scripts/run_phase6_questions.py

# Vérifier l'intégrité du journal d'audit immuable (détecte toute altération) :
uv run python -c "
import sys; sys.path.insert(0,'src'); sys.path.insert(0,'.')
from agent.audit.journal import verify_journal
print(verify_journal())
"
```

Le PDF final (`data/artifacts/reports/`) est entièrement traçable : chaque
`[Réf: index N]` du narratif pointe vers une ligne réelle du tableau en
annexe. Coût et tokens visibles dans le PDF, dans Langfuse
(http://localhost:3001), et dans `data/logs/immutable_journal.jsonl`.

### 14. Évaluation (Phase 7) — à exécuter vous-même

Commande unique et reproductible : exécute les 50 questions de référence
(`evaluation/eval_dataset.json`, SQL de référence validé pour chacune) à
travers le pipeline Text-to-SQL réel (Phase 1), calcule le **taux
d'exactitude d'exécution** (comparaison multi-ensemble des résultats,
indépendante des noms/ordre de colonnes - `agent/evaluation/scoring.py`),
plus les tests de robustesse (résistance à l'injection SQL, vérifiée sans
appel LLM ; colonnes inexistantes/hors périmètre/ambiguïté, à juger
manuellement sur la sortie réelle) et le coût Bedrock par catégorie de
question (business case). Effectue 50 vrais appels Bedrock :

```bash
export PYTHONPATH="src:."
uv run python scripts/run_phase7_evaluation.py
```

Produit un tableau d'exactitude par catégorie, un tableau de coût par
catégorie, le résultat des tests d'injection, et un rapport JSON complet
(`data/artifacts/eval_report.json`) avec le détail question par question.

## Architecture

| Couche | Choix | Statut |
|---|---|---|
| Génération LLM (SQL, Python, rapports, vision) | AWS Bedrock — Claude (API Converse) | ✅ Phase 0 |
| Embeddings (RAG schéma) | AWS Bedrock — Titan Embeddings v2 | ✅ Phase 0 |
| Base de données | PostgreSQL (Northwind) | ✅ Phase 0 |
| Export e-commerce imparfait | CSV/XLSX Online Retail II → Parquet | ✅ Phase 0 |
| API externe | Frankfurter (taux de change) | ✅ Phase 0 |
| Avis clients | Amazon Reviews (Kaggle) → Parquet | ✅ Phase 0 (nécessite credentials Kaggle) |
| Base vectorielle | Qdrant | ✅ Phase 1 (indexation du schéma) |
| Recherche hybride + validation SQL | SQLGlot, SQLFluff, rank-bm25 | ✅ Phase 1 |
| Stockage artefacts | MinIO (S3-compatible), URLs pré-signées | ✅ Phase 4 |
| Tâches asynchrones | Redis (+ Celery en Phase 6+) | ✅ Phase 0 (socle uniquement) |
| Observabilité | Langfuse (self-hosté) | ✅ Phase 0 |
| Sandbox exécution Python | Conteneur Docker isolé (réseau nul, quotas, non-root) | ✅ Phase 2 |
| Analyse | pandas, numpy, scipy, statsmodels, scikit-learn, polars | ✅ Phase 2 (dans le sandbox) |
| Graphiques | Plotly (export PNG via Kaleido + version interactive HTML) | ✅ Phase 3 (dans le sandbox) |
| Vision (lecture des graphes générés) | AWS Bedrock — Claude, API Converse multimodale | ✅ Phase 3 |
| Fichiers | XlsxWriter (Excel + graphique natif), CSV, WeasyPrint (PDF) | ✅ Phase 4 |
| Moteur analytique cross-source | DuckDB (attach Postgres + lecture Parquet) | ✅ Phase 5 |
| Résolution d'entités | Normalisation des pays entre sources (UDF DuckDB) | ✅ Phase 5 |
| Rapport narratif traçable | Bedrock + annexe de traçabilité (WeasyPrint) | ✅ Phase 6 |
| Journal d'audit immuable | Chaîne de hash (identité, tokens, coût) | ✅ Phase 6 |
| Suivi de coût Bedrock | Tarification par modèle + traces Langfuse | ✅ Phase 6 |
| Feedback utilisateur | Table Postgres `agent_feedback` (requêtes validées) | ✅ Phase 6 |
| Évaluation | 50 questions + SQL de référence, exactitude d'exécution | ✅ Phase 7 |
| Robustesse | Résistance à l'injection SQL (vérifiée sans LLM) | ✅ Phase 7 |
| Orchestration agentique | LangGraph | non planifiée dans les 7 phases |
| Frontend | Chainlit | non planifiée dans les 7 phases |

## Structure du projet

```
config/settings.py          Configuration centralisée (variables d'environnement)
src/agent/
  llm/                       Clients Bedrock (Claude via Converse, Titan Embeddings v2)
                              + protocols.py (Embedder, BedrockConverser) + extraction.py (blocs ```)
  db/                        Connexions Postgres (app, admin, lecture seule)
  ingestion/                 Scripts de chargement des 4 sources de données
  observability/             Client Langfuse, tarification Bedrock, TracedBedrockClient (Phase 6)
  health/                    Script de santé du socle
  schema/                    Introspection Postgres, indexation Qdrant, recherche hybride
  sql/                       Validateur (SQLGlot), exécuteur, générateur, pipeline, CLI
  sandbox/                   Runner d'exécution isolée (Docker : réseau nul, quotas, non-root)
  python_exec/               Générateur de code Python, pipeline avec auto-correction, CLI
  viz/                       Générateur de graphique Plotly, pipeline, vision, stockage, CLI
  export/                    Excel (XlsxWriter), CSV, PDF (WeasyPrint), upload MinIO, CLI
  federation/                Connexion DuckDB fédérée, résolution d'entités, devises,
                              introspection/générateur/pipeline/CLI cross-source, synthèse avis
  report/                    Générateur de rapport narratif traçable, export PDF, CLI (Phase 6)
  feedback/                  Base de feedback utilisateur - requêtes validées (Phase 6)
  evaluation/                Comparaison de résultats, robustesse, coût par catégorie (Phase 7)
  audit/                     Journal SQL/Python (accepté/rejeté/erreur) + journal.py (chaîne de hash)
sandbox/
  Dockerfile                 Image d'exécution (pandas/numpy/scipy/statsmodels/sklearn/plotly+Chrome)
  exec_wrapper.py            Exécuté dans le conteneur : charge df, exec(code), sérialise `result`/`fig`
infra/
  postgres/init/             Scripts d'init Postgres (bases + rôles)
  minio/                     Script de création des buckets
data/
  raw/                       Téléchargements bruts (gitignored)
  processed/                 Parquet nettoyés (gitignored)
  logs/anomalies/            Anomalies Online Retail II loguées (gitignored)
  logs/sql_audit.jsonl       Journal d'audit SQL (gitignored, généré à l'usage)
  logs/python_audit.jsonl    Journal d'audit du code Python et des graphiques (gitignored)
  logs/immutable_journal.jsonl  Journal d'audit immuable, chaîne de hash (gitignored)
  artifacts/charts/          Graphiques PNG + HTML générés (gitignored)
  artifacts/exports/         Fichiers Excel/CSV/PDF générés avant upload MinIO (gitignored)
  artifacts/reports/         Rapports PDF traçables générés avant upload MinIO (gitignored)
evaluation/                  Questions de validation par phase + eval_dataset.json (Phase 7,
                              50 questions + SQL de référence) + robustness_dataset.json
scripts/                     Scripts d'exécution manuelle (appels Bedrock réels)
tests/unit/                  Tests unitaires (Bedrock mocké ; Postgres/Qdrant/Docker/Langfuse réels)
```

## Sécurité

- Aucune credential AWS en dur : profil local ou variables d'environnement
  uniquement (voir `config/settings.py`)
- Rôle Postgres `agent_readonly` sans droit d'écriture — vérifié par
  `tests/unit` et par `healthcheck.py` (SELECT uniquement autorisé)
- Anomalies des données (IDs manquants, annulations, doublons) loguées et
  conservées, jamais supprimées silencieusement
- Tout échec de service est explicite (exception + message clair), jamais
  silencieux
- SQL généré par le LLM : une seule instruction, SELECT uniquement (DML/DDL
  rejetés), tables/colonnes vérifiées contre le schéma réel introspecté,
  LIMIT forcé (`agent/sql/validator.py`) — avant toute exécution
- Toute requête rejetée est loguée avec sa raison (`agent/audit/log.py`),
  jamais silencieusement ignorée
- Exécution du SQL généré exclusivement via le rôle Postgres
  `agent_readonly` (aucun droit d'écriture)
- Code Python généré exécuté uniquement dans le sandbox isolé
  (`agent/sandbox/runner.py`) : `--network none` (aucun accès réseau,
  y compris vers Bedrock — voir note dans `runner.py` sur cet écart assumé
  par rapport au choix initial "whitelist Bedrock"), FS racine en lecture
  seule, utilisateur non-root, capacités Linux supprimées, quotas
  CPU/RAM/PID, timeout dur avec `docker kill`
- Tout code Python exécuté est journalisé (`data/logs/python_audit.jsonl`),
  accepté ou en erreur, jamais silencieusement
- Le commentaire vision (Phase 3) est explicitement contraint par le prompt
  à ne décrire que ce qui est visible sur l'image réelle transmise, sans
  inventer de chiffre ou de tendance non lisible sur le graphique
- Les URLs d'accès aux fichiers exportés (Phase 4) sont pré-signées et
  expirent (24h par défaut) plutôt que de rendre le bucket public
- La fédération DuckDB (Phase 5) attache Postgres avec `READ_ONLY` et ne lit
  les Parquet qu'en lecture ; le même validateur SQL (garde-fous Phase 1,
  étendu au dialecte DuckDB et aux UNION/INTERSECT/EXCEPT) s'applique au SQL
  fédéré généré, avant toute exécution
- Journal d'audit immuable (Phase 6) : chaque entrée inclut le hash de la
  précédente ; `verify_journal()` détecte toute modification, suppression ou
  réordonnancement rétroactif d'une entrée (testé avec falsification réelle)
- Coût Bedrock jamais inventé : `estimate_cost()` retourne `None` pour un
  modèle absent de la table de tarification plutôt qu'un chiffre approximatif
- Chaque appel Bedrock tracé (Phase 6) est visible dans Langfuse avec son
  coût réel, indépendamment du journal immuable local
- Résistance à l'injection SQL (Phase 7) vérifiée avec une batterie de
  charges malveillantes (statements empilés, DROP/DELETE/UPDATE/TRUNCATE/
  GRANT, guillemets non fermés) passées directement au validateur - prouve
  que le garde-fou tient même dans l'hypothèse d'un LLM compromis ou trompé,
  indépendamment de ce que le modèle génère réellement en pratique
