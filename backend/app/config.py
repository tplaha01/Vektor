from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "Hybrid Trading Bot"
    ENV: str = "dev"
    BROKER: str = "paper"
    DATA_MODE: str = "live"

    TECH_WEIGHT: float = 0.35
    FUND_WEIGHT: float = 0.20
    SENT_WEIGHT: float = 0.20
    ML_WEIGHT:   float = 0.25

    WEBSOCKET_BROADCAST_INTERVAL: float = 2.0

    SECRET_KEY: str = "dev-secret"
    API_KEY: str = "dev-api-key"

    SQLITE_PATH: str = "trading_bot.db"

    NEWSAPI_KEY:  str | None = None
    FMP_KEY:      str | None = None
    FINNHUB_KEY:  str | None = None

    ALPACA_API_KEY:    str | None = None
    ALPACA_SECRET_KEY: str | None = None
    ALPACA_BASE_URL:   str = "https://paper-api.alpaca.markets"
    ALPACA_FEED:       str = "iex"

    BUY_THRESHOLD:  float = 0.20
    SELL_THRESHOLD: float = -0.20
    ATR_PERIOD:     int   = 14
    VOL_THRESHOLD:  float = 0.035

    # Set to your Vercel URL in production for CORS
    FRONTEND_URL: str | None = None

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()