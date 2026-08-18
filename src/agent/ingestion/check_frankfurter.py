"""Vérifie l'accès à l'API Frankfurter (taux de change, sans clé)."""

from __future__ import annotations

import logging
from typing import Any

import requests

from config.settings import get_settings

logger = logging.getLogger(__name__)


def check_frankfurter() -> dict[str, Any]:
    settings = get_settings()
    url = f"{settings.frankfurter_api_url}/latest"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    logger.info("Frankfurter OK: base=%s, %d taux reçus", payload["base"], len(payload["rates"]))
    return payload


def main() -> None:
    logging.basicConfig(level=get_settings().log_level)
    check_frankfurter()


if __name__ == "__main__":
    main()
