from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "Hybrid Trading Bot"
    ENV: str = "dev"
    BROKER: str = "paper"
    DATA_MODE: str = "live"

    # Signal weights (must sum to meaningful total — normalised in hybrid.py)
    TECH_WEIGHT: float = 0.35
    FUND_WEIGHT: float = 0.20
    SENT_WEIGHT: float = 0.20
    ML_WEIGHT:   float = 0.25   # Phase 3: LightGBM alpha

    WEBSOCKET_BROADCAST_INTERVAL: float = 2.0
    SECRET_KEY: str = "dev-secret"

    # Provider keys
    NEWSAPI_KEY:  str | None = None
    FMP_KEY:      str | None = None
    FINNHUB_KEY:  str | None = None

    # Alpaca
    ALPACA_API_KEY:    str | None = None
    ALPACA_SECRET_KEY: str | None = None
    ALPACA_BASE_URL:   str = "https://paper-api.alpaca.markets"
    ALPACA_FEED:       str = "iex"

    # Strategy tunables
    BUY_THRESHOLD:  float = 0.20
    SELL_THRESHOLD: float = -0.20
    ATR_PERIOD:     int   = 14
    VOL_THRESHOLD:  float = 0.035

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
