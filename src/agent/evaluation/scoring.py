"""Comparaison de résultats SQL pour l'exactitude d'exécution (Phase 7) :
compare le résultat d'une requête générée par le LLM au résultat d'une
requête de référence - la métrique standard d'évaluation text-to-SQL
(execution accuracy, ex: benchmark Spider).

Principes :
- Les lignes sont comparées comme un multi-ensemble (ordre des lignes
  ignoré, car SQL ne garantit aucun ordre sans ORDER BY explicite ; les
  doublons comptent - deux lignes identiques dans la référence doivent
  apparaître deux fois dans le résultat généré).
- Les valeurs D'UNE MÊME LIGNE ne sont jamais réordonnées entre elles :
  seul l'ordre des colonnes tel que retourné par chaque requête compte
  (permet d'ignorer les noms d'alias de colonnes, potentiellement
  différents entre le SQL de référence et le SQL généré, sans risquer de
  faire correspondre par erreur deux lignes différentes qui partageraient
  les mêmes valeurs dans un ordre différent).
- Un nombre de colonnes différent est toujours un échec (les deux requêtes
  ne répondent pas à la même question).
- Les flottants sont arrondis avant comparaison (tolérance)."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Any


def _round_value(value: Any, ndigits: int) -> Any:
    if isinstance(value, float):
        return round(value, ndigits)
    if isinstance(value, Decimal):
        return round(float(value), ndigits)
    return value


def _row_key(row: dict[str, Any], ndigits: int) -> tuple[Any, ...]:
    return tuple(_round_value(v, ndigits) for v in row.values())


def compare_results(
    reference_rows: list[dict[str, Any]],
    generated_rows: list[dict[str, Any]],
    float_ndigits: int = 4,
) -> bool:
    if not reference_rows and not generated_rows:
        return True
    if len(reference_rows) != len(generated_rows):
        return False

    ref_col_count = len(reference_rows[0])
    gen_col_count = len(generated_rows[0]) if generated_rows else 0
    if ref_col_count != gen_col_count:
        return False

    ref_multiset = Counter(_row_key(r, float_ndigits) for r in reference_rows)
    gen_multiset = Counter(_row_key(r, float_ndigits) for r in generated_rows)
    return ref_multiset == gen_multiset
