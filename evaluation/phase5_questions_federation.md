# Phase 5 — 8 questions de validation (analyse multi-sources)

Livrable vérifiable de la Phase 5 : chaque question nécessite une fédération
réelle entre Northwind (PostgreSQL) et Online Retail II (Parquet) via
DuckDB, avec résolution d'entités (noms de pays normalisés entre les deux
sources) et/ou conversion de devise (Online Retail II est en GBP, taux en
direct via Frankfurter injecté dans le prompt).

À exécuter par l'utilisateur lui-même (appel Bedrock réel : génération SQL
fédérée) :

```bash
export PYTHONPATH="src:."
uv run python scripts/run_phase5_questions.py
```

Ou une question à la fois :

```bash
uv run python -m agent.federation.cli \
  "Compare le nombre de commandes Northwind au nombre de lignes Online Retail II pour le Royaume-Uni et la France"
```

## Questions

1. Compare le nombre de commandes Northwind au nombre de lignes de commande Online Retail II pour le Royaume-Uni et la France (noms de pays normalisés).
2. Convertis le chiffre d'affaires total d'Online Retail II en USD au taux du jour, pour les 5 premiers pays par chiffre d'affaires.
3. Quels pays apparaissent dans Online Retail II mais jamais dans Northwind, une fois les noms de pays normalisés ?
4. Pour l'Irlande (EIRE dans Online Retail II, Ireland dans Northwind), compare le nombre de commandes entre les deux sources.
5. Quel est le chiffre d'affaires total (converti en USD) d'Online Retail II pour les 3 pays où Northwind a le plus de commandes ?
6. Combien de pays distincts (après normalisation) sont représentés dans chacune des deux sources ?
7. Union des pays des deux sources (normalisés) : liste les 10 premiers par nombre total de commandes/lignes combinées.
8. Si un échantillon d'avis clients est disponible (`--with-reviews`), quelle est la synthèse qualitative des avis ?

## Ce qui doit être vérifié pour chaque question

- Le SQL fédéré généré (dialecte DuckDB) est affiché, y compris les tentatives rejetées et corrigées automatiquement.
- La normalisation des pays (`normalize_country`) est utilisée quand la comparaison entre sources l'exige.
- Le taux de change (si utilisé) correspond au taux en direct affiché dans le contexte envoyé au modèle.
- Le résultat est plausible au regard des données réelles des deux sources.
- En cas d'échec après 3 tentatives, l'agent l'indique clairement plutôt que d'inventer une réponse.
