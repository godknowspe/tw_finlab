#!/bin/bash
# Kill any existing process on port 8000
kill -9 $(lsof -t -i:8000) 2>/dev/null
sleep 1

# Start the server with nohup and log to nohup_uvicorn.log
nohup /Users/godknows/.pyenv/versions/3.11.9/bin/python -m uvicorn src.web.server:app --port 8000 --host 0.0.0.0 --reload > nohup_uvicorn.log 2>&1 &
echo "Server started with nohup. Logs are written to nohup_uvicorn.log"
