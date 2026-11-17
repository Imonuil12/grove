#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Free ports 8000 and 5500 if occupied by previous instances
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:5500 | xargs kill -9 2>/dev/null

# Activate python virtual environment if present
if [ -d "$SCRIPT_DIR/venv" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Start the FastAPI backend
echo "Starting FastAPI backend..."
cd "$SCRIPT_DIR/app/backend"
python3 main.py &
BACKEND_PID=$!

# Start the frontend server
echo "Starting frontend server..."
cd "$SCRIPT_DIR/app/frontend"
python3 -m http.server 5500 &
FRONTEND_PID=$!

echo "=========================================="
echo "Backend running on http://127.0.0.1:8000"
echo "Frontend running on http://127.0.0.1:5500/index.html"
echo "API Docs available at http://127.0.0.1:8000/docs"
echo "=========================================="
echo "Press Ctrl+C to stop both servers."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" INT TERM EXIT
wait

