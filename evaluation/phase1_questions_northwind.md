# Phase 1 — 20 questions de validation (Northwind)

Livrable vérifiable de la Phase 1 : ces 20 questions doivent être répondues
correctement, avec le SQL généré affiché pour chacune. À exécuter par
l'utilisateur lui-même (appels Bedrock réels) :

```bash
export PYTHONPATH="src:."
uv run python -m agent.schema.indexer   # une seule fois, indexe le schéma
uv run python scripts/run_phase1_questions.py
```

Ou une question à la fois :

```bash
uv run python -m agent.sql.cli "Combien de clients y a-t-il au total ?"
```

## Questions

1. Combien de clients y a-t-il au total ?
2. Combien de commandes ont été passées en 1997 ?
3. Quels sont les 5 produits les plus chers (par prix unitaire) ?
4. Quel est le chiffre d'affaires total (quantité × prix unitaire) toutes commandes confondues ?
5. Quels sont les 10 clients ayant passé le plus de commandes ?
6. Quel est le nombre de commandes par pays d'expédition, trié du plus grand au plus petit ?
7. Quels employés ont géré le plus de commandes, et combien chacun ?
8. Quel est le produit le plus vendu en quantité totale ?
9. Quelle est la remise moyenne (discount) appliquée sur les commandes ?
10. Quels sont les 5 clients ayant généré le plus de chiffre d'affaires ?
11. Combien de produits sont actuellement en rupture de stock (units_in_stock = 0) ?
12. Quelle catégorie de produits génère le plus de chiffre d'affaires ?
13. Quel est le délai moyen (en jours) entre la date de commande et la date d'expédition ?
14. Quels transporteurs (shippers) ont été utilisés, et combien de commandes chacun a-t-il livrées ?
15. Quels sont les produits fournis par le fournisseur (supplier) "Exotic Liquids" ?
16. Quelles commandes n'ont jamais été expédiées (shipped_date NULL) ?
17. Quel est le montant total du fret (freight) payé par pays de destination ?
18. Quels clients n'ont jamais passé de commande ?
19. Quel est le nombre moyen de produits distincts par commande ?
20. Quels sont les 3 mois de l'année (tous exercices confondus) avec le plus grand nombre de commandes ?

## Ce qui doit être vérifié pour chaque question

- Le SQL généré est affiché (chaque tentative, y compris les rejets corrigés automatiquement).
- Le SQL final n'utilise que des tables/colonnes réelles de Northwind (garde-fou déjà testé en Phase 1, section validateur).
- Le résultat est plausible au regard des données Northwind.
- En cas d'échec après 3 tentatives, l'agent l'indique clairement plutôt que d'inventer une réponse.
