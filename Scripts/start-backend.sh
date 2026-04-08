#!/bin/bash
# Start FastAPI backend server with hot reload

cd "$(dirname "$0")/.."
source venv/Scripts/activate
python -m uvicorn src.viz.app:app --reload --host 127.0.0.1 --port 8000
