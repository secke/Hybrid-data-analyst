"""Extraction de blocs de code depuis une réponse LLM (```lang ... ``` ou
texte brut). Partagé entre la génération SQL et la génération Python."""

from __future__ import annotations

import re

_FENCE_RE = re.compile(r"```(?:\w+)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_fenced_code(text: str) -> str:
    """Retourne le contenu du premier bloc ```...``` trouvé, ou le texte
    brut nettoyé s'il n'y a pas de bloc."""
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()
