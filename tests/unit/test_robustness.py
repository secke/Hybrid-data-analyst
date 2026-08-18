"""Teste la résistance à l'injection SQL contre le vrai validateur et le
vrai schéma Northwind. Aucun appel LLM - simule ce que produirait un LLM
compromis/trompé."""

from __future__ import annotations

from agent.evaluation.robustness import (
    INJECTION_PAYLOADS,
    all_injections_blocked,
    run_injection_resistance_check,
)


def test_injection_payload_list_is_non_empty() -> None:
    assert len(INJECTION_PAYLOADS) >= 10


def test_all_injection_payloads_are_blocked() -> None:
    results = run_injection_resistance_check()
    assert len(results) == len(INJECTION_PAYLOADS)
    for result in results:
        assert result.blocked, f"Payload non bloqué: {result.payload!r} ({result.reason})"


def test_all_injections_blocked_helper() -> None:
    results = run_injection_resistance_check()
    assert all_injections_blocked(results) is True


def test_malformed_string_literal_does_not_crash_validator() -> None:
    # Régression Phase 7 : un guillemet non fermé ("'; DROP TABLE x; --")
    # faisait planter sqlglot avec une TokenError non capturée.
    results = run_injection_resistance_check()
    malformed = next(r for r in results if r.payload.startswith("';"))
    assert malformed.blocked
    assert malformed.reason is not None
