#!/bin/bash
# Kill FastAPI backend server (uvicorn on port 8000)

# Find and kill processes on port 8000
if command -v lsof &> /dev/null; then
    # Unix/Mac
    lsof -ti:8000 | xargs -r kill -9
elif command -v netstat &> /dev/null; then
    # Windows Git Bash
    netstat -ano | grep ":8000" | awk '{print $5}' | sort -u | xargs -r -I {} taskkill //PID {} //F
fi

echo "Backend server stopped (port 8000)"
