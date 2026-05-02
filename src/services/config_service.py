from sqlalchemy.orm import Session
from src.data.models import AppConfig

class ConfigService:
    def __init__(self, db_session: Session):
        self.db = db_session

    def get_config(self, key: str, default=None) -> str:
        config = self.db.query(AppConfig).filter(AppConfig.key == key).first()
        return config.value if config else default

    def set_config(self, key: str, value: str):
        config = self.db.query(AppConfig).filter(AppConfig.key == key).first()
        if config:
            config.value = value
        else:
            config = AppConfig(key=key, value=value)
            self.db.add(config)
        self.db.commit()

    def get_all_configs(self) -> dict:
        configs = self.db.query(AppConfig).all()
        return {c.key: c.value for c in configs}
