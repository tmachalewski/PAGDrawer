#!/bin/bash
# Kill FastAPI backend server (uvicorn on port 8000)

if command -v lsof &> /dev/null; then
    # Unix/Mac - kill process tree on port 8000
    lsof -ti:8000 | xargs -r kill -9
else
    # Windows Git Bash - kill all python processes to ensure no orphans
    # This is aggressive but reliable for dev environments
    taskkill //F //IM python.exe 2>/dev/null
fi

echo "Backend server stopped (port 8000)"
