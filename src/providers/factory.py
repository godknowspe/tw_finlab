from .base import BaseDataProvider


class ProviderFactory:
    """Providers are imported lazily so optional SDKs (shioaji, FinMind) are only needed when selected."""

    @classmethod
    def get_provider(cls, name: str, **kwargs) -> BaseDataProvider:
        name = name.lower()
        if name == "yfinance":
            from .yfinance_provider import YFinanceProvider
            return YFinanceProvider()
        if name == "shioaji":
            from .shioaji_provider import ShioajiProvider
            return ShioajiProvider(api_key=kwargs.get("api_key", ""), api_secret=kwargs.get("api_secret", ""))
        if name == "finmind":
            from .finmind_provider import FinMindProvider
            return FinMindProvider(token=kwargs.get("token"))
        raise ValueError(f"Unknown provider: {name}")
