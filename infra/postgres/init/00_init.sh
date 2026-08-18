#!/bin/bash
# Injecte les mots de passe des rôles applicatifs depuis les variables
# d'environnement du conteneur (jamais en dur dans le SQL versionné).
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
    -v app_pw="$AGENT_APP_PASSWORD" \
    -v ro_pw="$AGENT_READONLY_PASSWORD" \
    -f /docker-entrypoint-initdb.d/01_databases_and_roles.sql.template
