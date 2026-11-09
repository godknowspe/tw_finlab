import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.domain.symbols import canonical_symbol, currency_of, market_of


def normalize_timestamp(value) -> str:
    """Trades carry naive exchange-local time. Store a uniform ISO string so lexical and
    chronological order agree ('2026-06-01 10:00:00' and '2026-06-01T09:00' used to mis-sort)."""
    if isinstance(value, datetime.datetime):
        dt = value
    else:
        dt = datetime.datetime.fromisoformat(str(value).strip().replace(" ", "T"))
    if dt.tzinfo is not None:
        raise ValueError("timestamp must be exchange-local time without a UTC offset")
    return dt.isoformat(timespec="minutes" if dt.second == 0 and dt.microsecond == 0 else "seconds")


class Trade(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    symbol: str
    action: Literal["BUY", "SELL"]
    shares: int = Field(gt=0)
    price: float = Field(gt=0, allow_inf_nan=False)
    timestamp: str
    currency: Literal["TWD", "USD"]
    # Actual broker fee and transaction tax for this fill, in trade currency.
    fee: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    tax: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    source: Optional[str] = None
    source_trade_id: Optional[str] = None

    @field_validator("symbol")
    @classmethod
    def _symbol(cls, v: str) -> str:
        v = canonical_symbol(v)
        if not v:
            raise ValueError("symbol is empty")
        return v

    @field_validator("timestamp", mode="before")
    @classmethod
    def _timestamp(cls, v) -> str:
        return normalize_timestamp(v)

    @model_validator(mode="after")
    def _currency_matches_market(self):
        if self.currency != currency_of(self.symbol):
            raise ValueError(f"{self.symbol} trades in {currency_of(self.symbol)}, not {self.currency}")
        return self


class WatchlistItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    symbol: str
    name: str = ""
    ref_price: float = 0.0
    market: Literal["TW", "US"] = "TW"

    @field_validator("symbol")
    @classmethod
    def _symbol(cls, v: str) -> str:
        v = canonical_symbol(v)
        if not v:
            raise ValueError("symbol is empty")
        return v

    @model_validator(mode="after")
    def _market(self):
        self.market = market_of(self.symbol)
        return self


class Cash(BaseModel):
    model_config = ConfigDict(extra="allow")

    TWD: float = Field(default=1000000.0, allow_inf_nan=False)
    USD: float = Field(default=50000.0, allow_inf_nan=False)


class Settings(BaseModel):
    model_config = ConfigDict(extra="allow")

    usd_twd_rate: float = Field(default=32.5, gt=0, allow_inf_nan=False)


class AppState(BaseModel):
    # Unknown top-level keys (agent_state, data_sources, ...) are preserved on round-trip.
    model_config = ConfigDict(extra="allow")

    schema_version: int = 1
    settings: Settings = Field(default_factory=Settings)
    watchlist: List[WatchlistItem] = Field(default_factory=list)
    cash: Cash = Field(default_factory=Cash)
    trades: List[Trade] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique(self):
        ids = [t.id for t in self.trades]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate trade id")
        executions = [(t.source, t.source_trade_id) for t in self.trades if t.source_trade_id]
        if len(executions) != len(set(executions)):
            raise ValueError("duplicate broker execution (source, source_trade_id)")
        symbols = [w.symbol for w in self.watchlist]
        if len(symbols) != len(set(symbols)):
            raise ValueError("duplicate watchlist symbol")
        return self
