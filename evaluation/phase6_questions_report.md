# Phase 6 — 6 questions de validation (rapport traçable)

Livrable vérifiable de la Phase 6 : un rapport PDF complet, dont chaque
affirmation chiffrée référence une ligne vérifiable du tableau en annexe, et
dont chaque génération est journalisée (journal d'audit immuable, chaîne de
hash vérifiée) et tracée dans Langfuse (coût inclus).

À exécuter par l'utilisateur lui-même (appels Bedrock réels : génération SQL
puis génération narrative) :

```bash
export PYTHONPATH="src:."
uv run python scripts/run_phase6_questions.py
```

Ou une question à la fois :

```bash
uv run python -m agent.report.cli "Quel est le chiffre d'affaires total par catégorie de produits ?"
```

## Questions

1. Quel est le chiffre d'affaires total par catégorie de produits (Northwind) ?
2. Quels sont les 5 clients ayant généré le plus de chiffre d'affaires ?
3. Quel est le nombre de commandes par pays d'expédition ?
4. Quels employés ont géré le plus de commandes, et combien chacun ?
5. Quel est le produit le plus vendu en quantité totale ?
6. Quelle est la répartition du chiffre d'affaires par transporteur (shipper) ?

## Ce qui doit être vérifié pour chaque question

- Le PDF généré (`data/artifacts/reports/`) contient un narratif structuré où chaque chiffre cite `[Réf: index N]`.
- L'annexe de traçabilité contient le tableau complet et le SQL exécuté - chaque référence du narratif doit correspondre à une ligne réelle de ce tableau.
- Les métadonnées d'audit (identité, modèle, tokens, coût, hash du journal) sont présentes en fin de PDF.
- Après exécution, vérifiez l'intégrité du journal :
  ```bash
  uv run python -c "
  import sys; sys.path.insert(0,'src'); sys.path.insert(0,'.')
  from agent.audit.journal import verify_journal
  print(verify_journal())
  "
  ```
  Le résultat doit indiquer `ok=True` avec un `entry_count` égal au nombre de rapports générés.
- Dans Langfuse (http://localhost:3001), chaque génération apparaît avec son coût.
