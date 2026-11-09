#!/bin/bash
cd "$(dirname "$0")"

# Load PORTFOLIO_EXPORT_*, TW_FINLAB_STATE_FILE, TW_FINLAB_HOST, ... from the git-ignored .env
if [ -f .env ]; then
    set -a; . ./.env; set +a
fi

# The API has no authentication: bind to loopback unless TW_FINLAB_HOST says otherwise.
HOST=${TW_FINLAB_HOST:-127.0.0.1}
PORT=${TW_FINLAB_PORT:-8000}

PYTHON=./.venv/bin/python
[ -x "$PYTHON" ] || PYTHON=python3

kill $(lsof -t -i:"$PORT") 2>/dev/null
sleep 1

# No --reload: every reload re-runs the startup export. Pass --reload yourself when developing.
nohup "$PYTHON" -m uvicorn src.web.server:app --port "$PORT" --host "$HOST" "$@" > nohup_uvicorn.log 2>&1 &
echo "Server started on http://$HOST:$PORT (logs: nohup_uvicorn.log)"
