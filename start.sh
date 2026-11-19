#!/bin/bash
# Run Grove locally: migrate the database, then serve the API and the website on one port.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8000}"
[ -d "$SCRIPT_DIR/venv" ] && source "$SCRIPT_DIR/venv/bin/activate"
python "$SCRIPT_DIR/app/backend/manage_db.py" upgrade
cd "$SCRIPT_DIR/app/backend"
echo "Grove: http://127.0.0.1:$PORT  (API docs: /docs)"
exec uvicorn main:app --host 127.0.0.1 --port "$PORT"
