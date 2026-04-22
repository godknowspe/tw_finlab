kill -9 $(lsof -t -i:8000) 2>/dev/null
sleep 1
python -m uvicorn src.web.server:app --port 8000 --host 0.0.0.0 --reload 2>&1 > /dev/null &
