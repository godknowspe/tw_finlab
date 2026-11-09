from src.data.models import get_engine, get_session
from src.services.state_store import StateStore

# Set by server.py at startup; routers read them through these accessors.
_state: StateStore = None
_status = {}


def get_db():
    db = get_session(get_engine())
    try:
        yield db
    finally:
        db.close()


def state() -> StateStore:
    return _state


def sync_status() -> dict:
    return {name: getter() for name, getter in _status.items()}
