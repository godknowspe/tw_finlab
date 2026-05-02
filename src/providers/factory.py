from typing import Dict, Type, Optional
from .base import BaseDataProvider
from .yfinance_provider import YFinanceProvider
from .shioaji_provider import ShioajiProvider
from .finmind_provider import FinMindProvider

class ProviderFactory:
    @classmethod
    def get_provider(cls, name: str, **kwargs) -> BaseDataProvider:
        name = name.lower()
        if name == "yfinance":
            return YFinanceProvider()
        elif name == "shioaji":
            return ShioajiProvider(
                api_key=kwargs.get("api_key", ""),
                api_secret=kwargs.get("api_secret", "")
            )
        elif name == "finmind":
            return FinMindProvider(token=kwargs.get("token"))
        
        raise ValueError(f"Unknown provider: {name}")
