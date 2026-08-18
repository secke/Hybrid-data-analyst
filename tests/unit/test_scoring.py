from __future__ import annotations

from decimal import Decimal

from agent.evaluation.scoring import compare_results


def test_identical_rows_match() -> None:
    assert compare_results([{"a": 1, "b": 2}], [{"a": 1, "b": 2}]) is True


def test_different_column_names_still_match() -> None:
    assert compare_results([{"count": 5}], [{"n": 5}]) is True


def test_row_order_is_ignored() -> None:
    assert compare_results([{"a": 1}, {"a": 2}], [{"a": 2}, {"a": 1}]) is True


def test_duplicate_rows_are_counted_as_a_multiset() -> None:
    reference = [{"a": 1}, {"a": 1}, {"a": 2}]
    generated = [{"a": 1}, {"a": 2}]
    assert compare_results(reference, generated) is False


def test_different_row_count_fails() -> None:
    assert compare_results([{"a": 1}], [{"a": 1}, {"a": 2}]) is False


def test_different_column_count_fails() -> None:
    assert compare_results([{"a": 1, "b": 2}], [{"a": 1}]) is False


def test_float_values_within_tolerance_match() -> None:
    assert compare_results([{"x": 3.14159265}], [{"x": 3.1415927}]) is True


def test_float_values_outside_tolerance_do_not_match() -> None:
    assert compare_results([{"x": 3.1}], [{"x": 3.5}]) is False


def test_both_empty_results_match() -> None:
    assert compare_results([], []) is True


def test_one_empty_one_not_fails() -> None:
    assert compare_results([], [{"a": 1}]) is False


def test_intra_row_values_are_never_scrambled() -> None:
    # (a=5, b=10) et (a=10, b=5) partagent les mêmes valeurs mais dans un
    # ordre différent au sein de la ligne : ce ne sont PAS des lignes
    # équivalentes, la comparaison ne doit jamais les faire correspondre.
    assert compare_results([{"a": 5, "b": 10}], [{"a": 10, "b": 5}]) is False


def test_decimal_and_float_are_comparable() -> None:
    assert compare_results([{"x": Decimal("12.50")}], [{"x": 12.5}]) is True


def test_none_values_are_handled() -> None:
    assert compare_results([{"a": None}], [{"a": None}]) is True
    assert compare_results([{"a": None}], [{"a": 1}]) is False
