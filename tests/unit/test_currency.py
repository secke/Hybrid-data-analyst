"""Teste la conversion de devises. `fetch_rates` fait un vrai appel réseau à
Frankfurter (pas un appel LLM) ; `convert` est pure logique."""

from __future__ import annotations

import pytest

from agent.federation.currency import convert, fetch_rates

RATES_FROM_GBP = {"USD": 1.36, "EUR": 1.17}


def test_convert_same_currency_is_passthrough() -> None:
    assert convert(100.0, "GBP", "GBP", RATES_FROM_GBP) == 100.0


def test_convert_applies_rate() -> None:
    assert convert(100.0, "GBP", "USD", RATES_FROM_GBP) == pytest.approx(136.0)


def test_convert_raises_for_unknown_target_currency() -> None:
    with pytest.raises(ValueError, match="indisponible"):
        convert(10.0, "GBP", "ZZZ", RATES_FROM_GBP)


def test_fetch_rates_returns_real_rates() -> None:
    rates = fetch_rates("GBP")
    assert "USD" in rates
    assert "EUR" in rates
    assert rates["USD"] > 0
