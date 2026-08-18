"""Conversion de devises via l'API Frankfurter (taux en direct, sans clé).

Online Retail II est un commerçant britannique : ses montants sont en GBP.
Northwind (jeu de données classique) n'a pas de devise explicite - traité
comme USD par convention, pour permettre une comparaison chiffrée entre les
deux sources après conversion."""

from __future__ import annotations

import logging

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config.settings import get_settings

logger = logging.getLogger(__name__)


@retry(
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True,
)
def fetch_rates(base: str) -> dict[str, float]:
    """Taux de change en direct depuis `base` vers toutes les devises
    supportées par Frankfurter. Quelques tentatives avec backoff : l'API est
    parfois lente à répondre à une des IP résolues (observé en pratique)."""
    settings = get_settings()
    url = f"{settings.frankfurter_api_url}/latest"
    response = requests.get(url, params={"base": base}, timeout=10)
    response.raise_for_status()
    payload = response.json()
    rates: dict[str, float] = dict(payload["rates"])
    logger.info("Taux de change récupérés (base=%s): %d devises", base, len(rates))
    return rates


def convert(amount: float, from_currency: str, to_currency: str, rates: dict[str, float]) -> float:
    """`rates` doit être exprimé avec `from_currency` comme devise de base
    (voir `fetch_rates(from_currency)`)."""
    if from_currency == to_currency:
        return amount
    if to_currency not in rates:
        raise ValueError(f"Taux de change indisponible pour {from_currency} -> {to_currency}")
    return amount * rates[to_currency]
