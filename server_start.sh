kill -9 $(lsof -t -i:8000) 2>/dev/null
sleep 1
/Users/godknows/.pyenv/versions/3.11.9/bin/python -m uvicorn src.web.server:app --port 8000 --host 0.0.0.0 --reload 2>&1 > /dev/null &
