#!/bin/bash
# Start MongoDB container for PAGDrawer persistent caches.
# Data persists across restarts in the named volume pagdrawer_mongodb_data.

set -e
cd "$(dirname "$0")/.."

if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not on PATH." >&2
    exit 1
fi

# Prefer `docker compose` (v2). Fall back to `docker-compose` (v1).
if docker compose version &> /dev/null; then
    COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE="docker-compose"
else
    echo "ERROR: Neither 'docker compose' nor 'docker-compose' is available." >&2
    exit 1
fi

$COMPOSE up -d mongodb

# Wait up to ~20 s for Mongo to become reachable
echo "Waiting for MongoDB to accept connections..."
for i in $(seq 1 20); do
    if docker exec pagdrawer-mongo mongosh --quiet --eval 'db.runCommand({ ping: 1 })' &> /dev/null; then
        echo "MongoDB is ready on localhost:27017"
        exit 0
    fi
    sleep 1
done

echo "WARNING: MongoDB did not become ready within 20 s. Check 'docker logs pagdrawer-mongo'." >&2
exit 1
