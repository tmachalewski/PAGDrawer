#!/bin/bash
# Stop the MongoDB container. Data persists in the named volume
# pagdrawer_mongodb_data (remove it manually with `docker volume rm` if desired).

set -e
cd "$(dirname "$0")/.."

if docker compose version &> /dev/null; then
    COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE="docker-compose"
else
    echo "ERROR: Neither 'docker compose' nor 'docker-compose' is available." >&2
    exit 1
fi

$COMPOSE stop mongodb
echo "MongoDB container stopped. Data volume preserved."
