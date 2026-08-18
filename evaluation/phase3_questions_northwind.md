# Phase 3 — 8 questions de validation (graphique + relecture vision)

Livrable vérifiable de la Phase 3 : pour chaque question, un graphique
correct est produit dans le sandbox isolé (Phase 2/3), exporté en PNG, puis
Claude (Bedrock, vision) commente l'image PNG réellement générée — le
commentaire doit être cohérent avec ce qui est visible sur le graphique.

À exécuter par l'utilisateur lui-même (appels Bedrock réels : génération
SQL, génération du graphique, et vision) :

```bash
export PYTHONPATH="src:."
uv run python scripts/run_phase3_questions.py
```

Ou une paire à la fois :

```bash
uv run python -m agent.viz.cli \
  "Donne-moi le chiffre d'affaires total par catégorie de produits" \
  "Trace un graphique en barres du chiffre d'affaires par catégorie"
```

## Questions (SQL -> graphique)

1. SQL: Donne-moi le chiffre d'affaires (quantité x prix unitaire) total par catégorie de produits.
   Graphique: Trace un graphique en barres du chiffre d'affaires par catégorie.

2. SQL: Donne-moi le nombre de commandes par mois sur toute la période disponible.
   Graphique: Trace une courbe de l'évolution du nombre de commandes au fil des mois.

3. SQL: Donne-moi le nombre de commandes par pays de destination.
   Graphique: Trace un graphique en barres horizontales du nombre de commandes par pays, trié décroissant.

4. SQL: Donne-moi le prix unitaire et la quantité de chaque ligne de commande.
   Graphique: Trace un nuage de points (scatter) du prix unitaire en fonction de la quantité commandée.

5. SQL: Donne-moi le montant du fret de toutes les commandes.
   Graphique: Trace un histogramme de la distribution du montant du fret.

6. SQL: Donne-moi le chiffre d'affaires total généré par chaque employé.
   Graphique: Trace un graphique en barres du chiffre d'affaires par employé, trié décroissant.

7. SQL: Donne-moi la part du chiffre d'affaires total pour chacune des 5 plus grandes catégories de produits.
   Graphique: Trace un graphique en camembert (pie chart) de cette répartition.

8. SQL: Donne-moi le nombre de commandes gérées par chaque transporteur (shipper).
   Graphique: Trace un graphique en barres du nombre de commandes par transporteur.

## Ce qui doit être vérifié pour chaque question

- Le code du graphique généré est affiché (tentatives + corrections automatiques).
- Le graphique est exporté en PNG (`data/artifacts/charts/`) et en version interactive HTML.
- Le commentaire vision est cohérent avec ce qui est visible sur l'image (pas de chiffre inventé, pas de tendance non visible).
- En cas d'échec après 3 tentatives, l'agent l'indique clairement plutôt que d'inventer un graphique ou un commentaire.
