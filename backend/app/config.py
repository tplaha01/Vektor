from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "Hybrid Trading Bot"
    ENV: str = "dev"
    BROKER: str = "paper"
    LIVE_TRADING_ENABLED: bool = False
    LIVE_TRADING_REQUIRE_ALLOWLIST: bool = True
    LIVE_TRADING_SYMBOL_ALLOWLIST: str = ""
    LIVE_TRADING_ALPACA_ENABLED: bool = False
    LIVE_TRADING_OANDA_ENABLED: bool = False
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
    AGENT_RUNTIME_AUTOPILOT_DYNAMIC_UNIVERSE_ENABLED: bool = True
    AGENT_RUNTIME_AUTOPILOT_SCOUT_SYMBOLS: str = "SPY,QQQ,IWM,DIA,XLK,XLF,XLE,TLT,GLD,SLV,USO,UNG,AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,AMD"
    AGENT_RUNTIME_AUTOPILOT_SCOUT_MAX_SYMBOLS: int = 4
    AGENT_RUNTIME_SWARM_WAVE_SIZE: int = 2
    AGENT_RUNTIME_SWARM_WAVE_SPACING_SECONDS: float = 20.0
    AGENT_RUNTIME_SWARM_MAX_ACTIVE_PACKS: int = 2
    AGENT_RUNTIME_AUTOPILOT_DEFAULT_SIDE: str = "buy"
    AGENT_RUNTIME_AUTOPILOT_DEFAULT_QUANTITY: float = 1.0
    AGENT_RUNTIME_AUTOPILOT_SLEEVE: str = "tactical"
    AGENT_RUNTIME_SESSION_GUARD_ENABLED: bool = True
    AGENT_RUNTIME_BLOCK_TRADES_WHEN_CLOSED: bool = True
    AGENT_RUNTIME_MIN_TRADE_CONVICTION: float = 0.60
    AGENT_RUNTIME_ALLOW_CASH_HOLD: bool = True
    AGENT_RUNTIME_DISCOVERY_MIN_SCORE: float = 0.58
    AGENT_RUNTIME_DISCOVERY_MIN_CONFIDENCE: float = 0.55
    AGENT_RUNTIME_DISCOVERY_NEWS_LIMIT: int = 8
    DECISION_GATE_ML_ENABLED: bool = True
    DECISION_GATE_MIN_SCORE: float = 0.58
    DECISION_GATE_MIN_CONFIDENCE: float = 0.55
    DECISION_GATE_MIN_REGIME_ALIGNMENT: float = 0.52
    DECISION_GATE_MIN_LIQUIDITY_SCORE: float = 0.35
    DECISION_GATE_MAX_NEWS_INTENSITY_COUNT: int = 10
    DECISION_GATE_ASSET_CLASS_PROFILES: str = """
    {
      "equities": {
        "min_liquidity_score": 0.4
      },
      "options": {
        "min_score": 0.64,
        "min_confidence": 0.62,
        "min_regime_alignment": 0.58,
        "min_liquidity_score": 0.45,
        "max_news_intensity_count": 7
      },
      "forex": {
        "min_score": 0.56,
        "min_confidence": 0.53,
        "min_regime_alignment": 0.55,
        "min_liquidity_score": 0.45,
        "max_news_intensity_count": 9
      },
      "crypto": {
        "min_score": 0.63,
        "min_confidence": 0.6,
        "min_regime_alignment": 0.58,
        "min_liquidity_score": 0.5,
        "max_news_intensity_count": 6
      },
      "commodities": {
        "min_score": 0.6,
        "min_confidence": 0.57,
        "min_regime_alignment": 0.55,
        "min_liquidity_score": 0.42,
        "max_news_intensity_count": 8
      }
    }
    """
    DECISION_GATE_STRATEGY_FAMILY_PROFILES: str = """
    {
      "technical": {
        "min_score": 0.56,
        "min_confidence": 0.53
      },
      "fundamental": {
        "min_score": 0.6,
        "min_confidence": 0.58
      },
      "sentiment": {
        "min_confidence": 0.57,
        "max_news_intensity_count": 14
      },
      "multi_signal_scout": {
        "min_score": 0.62,
        "min_confidence": 0.58,
        "min_regime_alignment": 0.56
      },
      "event_driven": {
        "min_score": 0.66,
        "min_confidence": 0.62,
        "max_news_intensity_count": 5
      },
      "macro": {
        "min_score": 0.61,
        "min_confidence": 0.58,
        "min_regime_alignment": 0.6
      }
    }
    """
    DECISION_GATE_ASSET_STRATEGY_PROFILES: str = """
    {
      "options:event_driven": {
        "min_score": 0.7,
        "min_confidence": 0.66,
        "min_regime_alignment": 0.62,
        "min_liquidity_score": 0.5,
        "max_news_intensity_count": 4
      },
      "crypto:multi_signal_scout": {
        "min_score": 0.67,
        "min_confidence": 0.62,
        "min_regime_alignment": 0.6,
        "min_liquidity_score": 0.55,
        "max_news_intensity_count": 5
      },
      "forex:macro": {
        "min_score": 0.59,
        "min_confidence": 0.56,
        "min_regime_alignment": 0.62,
        "min_liquidity_score": 0.48,
        "max_news_intensity_count": 8
      }
    }
    """
    FUND_DEFAULT_CAPITAL_USD: float = 500000.0
    FUND_DEFAULT_RESERVE_CASH_USD: float = 50000.0
    FUND_DEFAULT_SLEEVE_WEIGHTS: str = "long_term=0.5,recurring=0.3,tactical=0.2"
    CEO_DIGEST_ENABLED: bool = True
    CEO_DIGEST_INTERVAL_SECONDS: int = 21600
    CEO_APPROVAL_REQUIRED_FOR_TRADES: bool = True
    CEO_APPROVAL_REQUIRED_FOR_ALLOCATION_CHANGES: bool = True
    CEO_APPROVAL_REQUIRED_FOR_PUBLIC_PUBLICATION: bool = True
    CEO_APPROVAL_REQUIRED_FOR_MAJOR_REROUTES: bool = True

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
    AI_ROLE_MODEL_BLOG: str | None = None
    AI_ROLE_MODEL_FUND_MANAGER: str | None = None
    AI_ROLE_MODEL_COMPOSITE_SYNTHESIS: str | None = None
    AI_ROLE_MODEL_RESEARCH_JUDGE: str | None = None
    AI_ROLE_REQUIRE_SUCCESS: bool = False
    AI_ROLE_ROUTER_ENABLED: bool = False
    AI_ROLE_GATEWAY_ENABLED: bool = False
    AI_ROLE_GATEWAY_BASE_URL: str | None = None
    AI_ROLE_ROUTE_DEFAULT: str = "gemini_flash_lite,groq"
    AI_ROLE_ROUTE_TECHNICAL: str = "gemini_flash_lite,groq"
    AI_ROLE_ROUTE_FUNDAMENTAL: str = "gemini_flash_lite,groq"
    AI_ROLE_ROUTE_SENTIMENT: str = "gemini_flash_lite,groq"
    AI_ROLE_ROUTE_ML: str = "gemini_flash,groq"
    AI_ROLE_ROUTE_INSIGHT: str = "gemini_flash_lite,groq"
    AI_ROLE_ROUTE_HEDGE_FUND: str = "gemini_flash,groq"
    AI_ROLE_ROUTE_FUND_MANAGER: str = "gemini_flash,groq"
    AI_ROLE_ROUTE_COMPOSITE_SYNTHESIS: str = "gemini_flash,groq"
    AI_ROLE_ROUTE_RESEARCH_JUDGE: str = "gemini_flash,groq"
    AI_ROLE_ROUTE_BLOG: str = "gemini_flash,groq"
    AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_ENABLED: bool = True
    AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_TYPE: str = "openai_compatible"
    AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_API_KEY: str | None = None
    AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_MODEL: str = "gemini-2.5-flash-lite"
    AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_MAX_CONCURRENCY: int = 1
    AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_COOLDOWN_SECONDS: float = 45.0
    AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_TRANSIENT_COOLDOWN_SECONDS: float = 8.0
    AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_REQUESTS_PER_WINDOW: int = 5
    AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_TOKENS_PER_WINDOW: int = 12000
    AI_ROLE_PROVIDER_GEMINI_FLASH_LITE_WINDOW_SECONDS: float = 60.0
    AI_ROLE_PROVIDER_GEMINI_FLASH_ENABLED: bool = True
    AI_ROLE_PROVIDER_GEMINI_FLASH_TYPE: str = "openai_compatible"
    AI_ROLE_PROVIDER_GEMINI_FLASH_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    AI_ROLE_PROVIDER_GEMINI_FLASH_API_KEY: str | None = None
    AI_ROLE_PROVIDER_GEMINI_FLASH_MODEL: str = "gemini-2.5-flash"
    AI_ROLE_PROVIDER_GEMINI_FLASH_MAX_CONCURRENCY: int = 1
    AI_ROLE_PROVIDER_GEMINI_FLASH_COOLDOWN_SECONDS: float = 45.0
    AI_ROLE_PROVIDER_GEMINI_FLASH_TRANSIENT_COOLDOWN_SECONDS: float = 8.0
    AI_ROLE_PROVIDER_GEMINI_FLASH_REQUESTS_PER_WINDOW: int = 5
    AI_ROLE_PROVIDER_GEMINI_FLASH_TOKENS_PER_WINDOW: int = 18000
    AI_ROLE_PROVIDER_GEMINI_FLASH_WINDOW_SECONDS: float = 60.0
    AI_ROLE_PROVIDER_GROQ_ENABLED: bool = True
    AI_ROLE_PROVIDER_GROQ_TYPE: str = "openai_compatible"
    AI_ROLE_PROVIDER_GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    AI_ROLE_PROVIDER_GROQ_API_KEY: str | None = None
    AI_ROLE_PROVIDER_GROQ_MODEL: str = "openai/gpt-oss-20b"
    AI_ROLE_PROVIDER_GROQ_MAX_CONCURRENCY: int = 1
    AI_ROLE_PROVIDER_GROQ_COOLDOWN_SECONDS: float = 30.0
    AI_ROLE_PROVIDER_GROQ_TRANSIENT_COOLDOWN_SECONDS: float = 6.0
    AI_ROLE_PROVIDER_GROQ_REQUESTS_PER_WINDOW: int = 8
    AI_ROLE_PROVIDER_GROQ_TOKENS_PER_WINDOW: int = 20000
    AI_ROLE_PROVIDER_GROQ_WINDOW_SECONDS: float = 60.0
    AI_ROLE_PROVIDER_GITHUB_MODELS_ENABLED: bool = False
    AI_ROLE_PROVIDER_GITHUB_MODELS_TYPE: str = "openai_compatible"
    AI_ROLE_PROVIDER_GITHUB_MODELS_BASE_URL: str = "https://models.inference.ai.azure.com"
    AI_ROLE_PROVIDER_GITHUB_MODELS_API_KEY: str | None = None
    AI_ROLE_PROVIDER_GITHUB_MODELS_MODEL: str = "gpt-4.1-mini"
    AI_ROLE_PROVIDER_GITHUB_MODELS_MAX_CONCURRENCY: int = 1
    AI_ROLE_PROVIDER_GITHUB_MODELS_COOLDOWN_SECONDS: float = 30.0
    AI_ROLE_PROVIDER_GITHUB_MODELS_TRANSIENT_COOLDOWN_SECONDS: float = 6.0
    AI_ROLE_PROVIDER_GITHUB_MODELS_REQUESTS_PER_WINDOW: int = 4
    AI_ROLE_PROVIDER_GITHUB_MODELS_TOKENS_PER_WINDOW: int = 12000
    AI_ROLE_PROVIDER_GITHUB_MODELS_WINDOW_SECONDS: float = 60.0
    AI_ROLE_RUN_REQUEST_ENVELOPE: int = 8
    AI_ROLE_RUN_TOKENS_ENVELOPE: int = 18000
    AI_ROLE_RUN_WINDOW_SECONDS: float = 120.0
    AI_ROLE_DEFER_BASE_SECONDS: float = 15.0
    AI_ROLE_DEFER_BACKOFF_MULTIPLIER: float = 2.0
    AI_ROLE_DEFER_MAX_SECONDS: float = 900.0
    BLOG_AUTO_EDITORIAL_ENABLED: bool = True
    BLOG_AUTO_EDITORIAL_INTERVAL_HOURS: int = 12
    BLOG_AUTO_EDITORIAL_TARGET_PER_DAY: int = 2
    BLOG_AUTO_EDITORIAL_MIN_CONFIDENCE: float = 0.55
    BLOG_MARKET_REPORT_SCHEDULER_INTERVAL_SECONDS: int = 300
    BLOG_PREMARKET_REPORT_ENABLED: bool = True
    BLOG_PREMARKET_REPORT_LEAD_MINUTES: int = 30
    BLOG_POSTMARKET_REPORT_ENABLED: bool = True
    BLOG_POSTMARKET_REPORT_DELAY_MINUTES: int = 20
    BLOG_WEEKAHEAD_REPORT_ENABLED: bool = True
    BLOG_WEEKAHEAD_REPORT_WEEKDAY: str = "SUN"
    BLOG_WEEKAHEAD_REPORT_HOUR_ET: int = 18
    BLOG_WEEKAHEAD_REPORT_MINUTE_ET: int = 0
    BLOG_MARKET_REPORT_SYMBOLS: str = "SPY,QQQ,IWM,DIA,AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,AMD,GLD,SLV,TLT,USO,UNG"
    PERFORMANCE_TRACKER_ENABLED: bool = True
    PERFORMANCE_TRACKER_INTERVAL_SECONDS: int = 900
    PERFORMANCE_TRACKER_BENCHMARKS: str = "SPY,QQQ,GLD,TLT"

    NEWSAPI_KEY:  str | None = None
    FMP_KEY:      str | None = None
    FINNHUB_KEY:  str | None = None

    ALPACA_API_KEY:    str | None = None
    ALPACA_SECRET_KEY: str | None = None
    ALPACA_BASE_URL:   str = "https://paper-api.alpaca.markets"
    ALPACA_LIVE_BASE_URL: str = "https://api.alpaca.markets"
    ALPACA_FEED:       str = "iex"
    ALPACA_STREAM_ENABLED: bool = True
    ALPACA_HTTP_TIMEOUT_SECONDS: float = 8.0
    ALPACA_HTTP_RETRIES: int = 3
    ALPACA_HTTP_RETRY_BACKOFF_SECONDS: float = 0.75
    WEBSOCKET_STREAM_FETCH_TIMEOUT_SECONDS: float = 1.5
    OANDA_API_TOKEN: str | None = None
    OANDA_ACCOUNT_ID: str | None = None
    OANDA_BASE_URL: str = "https://api-fxpractice.oanda.com"
    OANDA_LIVE_BASE_URL: str = "https://api-fxtrade.oanda.com"
    OANDA_HTTP_TIMEOUT_SECONDS: float = 8.0

    BUY_THRESHOLD:  float = 0.20
    SELL_THRESHOLD: float = -0.20
    ATR_PERIOD:     int   = 14
    VOL_THRESHOLD:  float = 0.035

    # Set to your Vercel URL in production for CORS
    FRONTEND_URL: str | None = None
    SENTRY_DSN: str | None = None
    SENTRY_ENVIRONMENT: str = "production"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0
    SENTRY_PROFILES_SAMPLE_RATE: float = 0.0

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
