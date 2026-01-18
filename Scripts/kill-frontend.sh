#!/bin/bash
# Kill Vite frontend dev server (typically port 3000 or 3001)

# Find and kill processes on port 3000 and 3001
if command -v lsof &> /dev/null; then
    # Unix/Mac
    lsof -ti:3000 | xargs -r kill -9
    lsof -ti:3001 | xargs -r kill -9
elif command -v netstat &> /dev/null; then
    # Windows Git Bash
    netstat -ano | grep ":3000\|:3001" | awk '{print $5}' | sort -u | xargs -r -I {} taskkill //PID {} //F
fi

echo "Frontend server stopped (ports 3000, 3001)"
