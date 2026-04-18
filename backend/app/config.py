from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "Hybrid Trading Bot"
    ENV: str = "dev"
    BROKER: str = "paper"
    DATA_MODE: str = "live"
    REAL_DATA_STRICT_MODE: bool = False

    TECH_WEIGHT: float = 0.35
    FUND_WEIGHT: float = 0.20
    SENT_WEIGHT: float = 0.20
    ML_WEIGHT:   float = 0.25

    WEBSOCKET_BROADCAST_INTERVAL: float = 2.0
    AUTO_TRADING_ENABLED: bool = False
    AGENT_RUNTIME_ENABLED: bool = True
    AGENT_RUNTIME_POLL_INTERVAL_SECONDS: float = 1.5
    AGENT_RUNTIME_AUTOPILOT_ENABLED: bool = True
    AGENT_RUNTIME_AUTOPILOT_INTERVAL_SECONDS: float = 120.0
    AGENT_RUNTIME_AUTOPILOT_SYMBOLS: str = "AAPL,MSFT,NVDA,SPY"
    AGENT_RUNTIME_AUTOPILOT_DEFAULT_SIDE: str = "buy"
    AGENT_RUNTIME_AUTOPILOT_DEFAULT_QUANTITY: float = 1.0
    AGENT_RUNTIME_AUTOPILOT_SLEEVE: str = "tactical"
    FUND_DEFAULT_CAPITAL_USD: float = 500000.0
    FUND_DEFAULT_RESERVE_CASH_USD: float = 50000.0
    FUND_DEFAULT_SLEEVE_WEIGHTS: str = "long_term=0.5,recurring=0.3,tactical=0.2"

    SECRET_KEY: str = "dev-secret"
    API_KEY: str = "dev-api-key"

    SQLITE_PATH: str = "trading_bot.db"
    OPENCLAW_INGEST_TOKEN: str | None = None
    OPENCLAW_COMMANDS_ENABLED: bool = True
    OPENCLAW_COMMAND_TOKEN: str | None = None
    OPENCLAW_COMMAND_DEFAULT_AGENT_ID: str = "ceo"
    OPENCLAW_COMMAND_CHANNEL_ALLOWLIST: str | None = None
    OPENCLAW_COMMAND_SENDER_ALLOWLIST: str | None = None
    OPENCLAW_COMMAND_ROLE_ALLOWLIST: str = (
        "technical_analyst,fundamental_analyst,sentiment_analyst,ml_timeseries_analyst,"
        "insight_researcher,hedge_fund_researcher,fund_manager,trader,risk_auditor,signal_swarm,blog_writer"
    )
    OPENCLAW_COMMAND_CHANNEL_ROLE_POLICIES: str | None = None
    OPENCLAW_COMMAND_MAX_TEXT_LENGTH: int = 4000
    OPENCLAW_FUND_MANAGER_MODE: bool = True
    OPENCLAW_FUND_MANAGER_AGENT_ID: str = "fund_manager"
    OPENCLAW_FUND_MANAGER_ASSIGNED_ROLES: str = (
        "technical_analyst,fundamental_analyst,sentiment_analyst,ml_timeseries_analyst,"
        "insight_researcher,hedge_fund_researcher"
    )
    KNOWLEDGE_GRAPH_ENABLED: bool = True
    KNOWLEDGE_GRAPH_DIR: str = "knowledge_graph"
    KNOWLEDGE_GRAPH_MAX_EVENTS: int = 50_000
    KNOWLEDGE_GRAPH_PERSIST: bool = True
    GRAPHIFY_SYNC_ENABLED: bool = False
    GRAPHIFY_SYNC_MIN_INTERVAL_SECONDS: int = 30
    GRAPHIFY_UPDATE_COMMAND: str = "py -3 -m graphify update ."
    AI_ROLE_ADAPTER_ENABLED: bool = False
    AI_ROLE_PROVIDER: str = "openai_compatible"
    AI_ROLE_API_BASE_URL: str = "https://api.openai.com/v1"
    AI_ROLE_API_KEY: str | None = None
    AI_ROLE_TIMEOUT_SECONDS: int = 20
    AI_ROLE_TEMPERATURE: float = 0.1
    AI_ROLE_MAX_TOKENS: int = 700
    AI_ROLE_MODEL_DEFAULT: str = "gpt-4.1-mini"
    AI_ROLE_MODEL_TECHNICAL: str | None = None
    AI_ROLE_MODEL_FUNDAMENTAL: str | None = None
    AI_ROLE_MODEL_SENTIMENT: str | None = None
    AI_ROLE_MODEL_ML: str | None = None
    AI_ROLE_MODEL_INSIGHT: str | None = None
    AI_ROLE_MODEL_HEDGE_FUND: str | None = None
    AI_ROLE_REQUIRE_SUCCESS: bool = False

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
