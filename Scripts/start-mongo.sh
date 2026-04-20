#!/bin/bash
# Start MongoDB container for PAGDrawer persistent caches.
# Data persists across restarts in the named volume pagdrawer_mongodb_data.

cd "$(dirname "$0")/.."

# --- Pre-flight checks with clear diagnostics ---

if ! command -v docker &> /dev/null; then
    echo "ERROR: 'docker' command not found on PATH." >&2
    echo "Install Docker Desktop from https://www.docker.com/products/docker-desktop" >&2
    read -p "Press Enter to close..."
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "ERROR: Docker daemon is not responding." >&2
    echo "On Windows/Mac, make sure Docker Desktop is running (check system tray)." >&2
    echo "Then re-run this script." >&2
    read -p "Press Enter to close..."
    exit 1
fi

# Prefer `docker compose` (v2). Fall back to `docker-compose` (v1).
if docker compose version &> /dev/null; then
    COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE="docker-compose"
else
    echo "ERROR: Neither 'docker compose' nor 'docker-compose' is available." >&2
    echo "Docker Desktop ships with compose v2. Update Docker Desktop if missing." >&2
    read -p "Press Enter to close..."
    exit 1
fi

echo "Using: $COMPOSE"
echo "Pulling mongo:7 (first run may take a few minutes, ~700 MB)..."
if ! $COMPOSE pull mongodb; then
    echo "ERROR: Failed to pull mongo:7 image." >&2
    read -p "Press Enter to close..."
    exit 1
fi

echo "Starting MongoDB container..."
if ! $COMPOSE up -d mongodb; then
    echo "ERROR: 'docker compose up -d mongodb' failed. See output above." >&2
    read -p "Press Enter to close..."
    exit 1
fi

# Wait up to ~30 s for Mongo to become reachable
echo "Waiting for MongoDB to accept connections..."
for i in $(seq 1 30); do
    if docker exec pagdrawer-mongo mongosh --quiet --eval 'db.runCommand({ ping: 1 })' &> /dev/null; then
        echo "MongoDB is ready on localhost:27017"
        exit 0
    fi
    sleep 1
    echo "  (still starting... $i/30)"
done

echo "WARNING: MongoDB did not respond within 30 s." >&2
echo "Check logs with: docker logs pagdrawer-mongo" >&2
read -p "Press Enter to close..."
exit 1
