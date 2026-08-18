# Phase 2 — 10 questions de validation (calcul au-delà du SQL)

Livrable vérifiable de la Phase 2 : ces questions nécessitent un calcul que
le SQL seul n'exprime pas naturellement (corrélation, régression, z-score,
moyenne mobile, percentile, concentration...). Chaque question est un
couple : une requête SQL (Phase 1) pour récupérer les données brutes, puis
un calcul Python (Phase 2) exécuté dans le sandbox isolé sur le résultat.

À exécuter par l'utilisateur lui-même (appels Bedrock réels) :

```bash
export PYTHONPATH="src:."
uv run python scripts/run_phase2_questions.py
```

Ou une paire à la fois :

```bash
uv run python -m agent.python_exec.cli \
  "Donne-moi la quantité et le prix unitaire de chaque ligne de commande" \
  "Calcule la corrélation entre le prix unitaire et la quantité commandée"
```

## Questions (SQL -> calcul)

1. SQL: Donne-moi la date et le fret (freight) de toutes les commandes.
   Calcul: Calcule le taux de croissance mensuel (%) du fret total, mois par mois.

2. SQL: Donne-moi la quantité et le prix unitaire de chaque ligne de commande (order_details).
   Calcul: Calcule le coefficient de corrélation entre le prix unitaire et la quantité commandée.

3. SQL: Donne-moi le montant du fret de toutes les commandes.
   Calcul: Calcule la moyenne, l'écart-type, et liste les commandes dont le fret est une valeur aberrante (z-score > 3).

4. SQL: Donne-moi le nombre de commandes gérées par chaque employé.
   Calcul: Calcule l'écart-type et le coefficient de variation du nombre de commandes entre employés.

5. SQL: Donne-moi la quantité, le prix unitaire et la remise de chaque ligne de commande, avec l'identifiant client de la commande associée.
   Calcul: Calcule le chiffre d'affaires par client puis la part cumulative du chiffre d'affaires (triée décroissante) pour vérifier une éventuelle règle des 80/20.

6. SQL: Donne-moi le prix unitaire et la remise (discount) de chaque ligne de commande.
   Calcul: Calcule la régression linéaire (pente et R²) entre la remise et le prix unitaire.

7. SQL: Donne-moi la date de commande et le fret de toutes les commandes, triées par date.
   Calcul: Calcule la moyenne mobile sur 7 commandes du fret.

8. SQL: Donne-moi la quantité commandée pour chaque ligne de commande, avec le nom du produit associé.
   Calcul: Calcule le 90e percentile de la quantité commandée par produit.

9. SQL: Donne-moi la date de commande et la date d'expédition de toutes les commandes expédiées.
   Calcul: Calcule la médiane et les quartiles du délai de livraison (en jours), et identifie les valeurs aberrantes.

10. SQL: Donne-moi le montant du fret par pays de destination.
    Calcul: Calcule l'indice de concentration Herfindahl-Hirschman du fret total entre pays.

## Ce qui doit être vérifié pour chaque question

- Le code Python généré est affiché (chaque tentative, y compris les rejets/erreurs corrigés automatiquement).
- Le code s'exécute dans le sandbox isolé (`agent.sandbox.runner`), jamais en dehors.
- Le résultat est plausible au regard des données Northwind.
- En cas d'échec après 3 tentatives, l'agent l'indique clairement plutôt que d'inventer une réponse.
