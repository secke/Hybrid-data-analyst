from __future__ import annotations

from agent.federation.entity_resolution import normalize_country


def test_normalize_country_uk_alias() -> None:
    assert normalize_country("UK") == "United Kingdom"


def test_normalize_country_eire_alias() -> None:
    assert normalize_country("EIRE") == "Ireland"


def test_normalize_country_rsa_alias() -> None:
    assert normalize_country("RSA") == "South Africa"


def test_normalize_country_passthrough_for_unknown() -> None:
    assert normalize_country("France") == "France"
    assert normalize_country("Germany") == "Germany"


def test_normalize_country_strips_whitespace() -> None:
    assert normalize_country("  UK  ") == "United Kingdom"


def test_normalize_country_handles_none() -> None:
    assert normalize_country(None) is None
