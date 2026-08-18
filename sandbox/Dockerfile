# Image d'exécution isolée pour le code Python généré par le LLM (Phase 2).
# Isolation assurée au niveau du conteneur (réseau, ressources, FS) via les
# flags `docker run` dans src/agent/sandbox/runner.py - cette image ne fait
# qu'embarquer l'interpréteur et les libs d'analyse nécessaires.
FROM python:3.12-slim

# Dépendances système du Chrome headless utilisé par kaleido (export PNG des
# graphiques Plotly, Phase 3).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    pandas \
    numpy \
    scipy \
    statsmodels \
    scikit-learn \
    polars \
    pyarrow \
    plotly \
    kaleido \
    matplotlib

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin sandboxuser

# Kaleido >=1.0 ne bundle plus Chrome : il faut le télécharger au build (le
# sandbox tourne sans réseau à l'exécution - voir runner.py). Installé pour
# l'utilisateur sandbox puisque c'est lui qui l'invoquera au runtime.
USER sandboxuser
RUN plotly_get_chrome -y

WORKDIR /workspace
