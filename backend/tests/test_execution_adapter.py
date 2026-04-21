from app.broker.paper import PaperBroker
from app.config import get_settings
import app.fund.execution_adapter as execution_adapter_module
from app.fund.execution_adapter import execute_approved_intent


def _broker() -> PaperBroker:
    broker = PaperBroker()
    broker._db_ready = False
    return broker


def test_execute_approved_intent_supports_paper_crypto():
    broker = _broker()
    result = execute_approved_intent(
        {
            "symbol": "BTC-USD",
            "side": "buy",
            "quantity": 0.1,
            "approved": True,
            "decision_id": "dec-crypto",
            "risk_id": "risk-crypto",
            "price": 65000.0,
            "asset_class": "crypto",
            "routing_mode": "paper_crypto",
            "instrument_type": "crypto_spot",
        },
        broker=broker,
    )
    assert result["status"] == "executed"
    assert result["routing_mode"] == "paper_crypto"
    assert broker.positions["BTC-USD"]["asset_class"] == "crypto"


def test_execute_approved_intent_supports_paper_forex():
    broker = _broker()
    result = execute_approved_intent(
        {
            "symbol": "EUR/USD",
            "side": "buy",
            "quantity": 1000,
            "approved": True,
            "decision_id": "dec-fx",
            "risk_id": "risk-fx",
            "price": 1.08,
            "asset_class": "forex",
            "routing_mode": "paper_forex",
            "instrument_type": "fx_spot",
        },
        broker=broker,
    )
    assert result["status"] == "executed"
    assert result["cash_notional"] > 1000.0
    assert broker.positions["EUR/USD"]["instrument_type"] == "fx_spot"


def test_execute_approved_intent_supports_paper_options():
    broker = _broker()
    result = execute_approved_intent(
        {
            "symbol": "AAPL260619C00210000",
            "side": "buy",
            "quantity": 1,
            "approved": True,
            "decision_id": "dec-opt",
            "risk_id": "risk-opt",
            "price": 5.25,
            "asset_class": "options",
            "routing_mode": "paper_options",
            "instrument_type": "option_contract",
            "underlier_symbol": "AAPL",
        },
        broker=broker,
    )
    assert result["status"] == "executed"
    assert result["cash_notional"] >= 525.0
    assert broker.positions["AAPL260619C00210000"]["contract_multiplier"] == 100.0


def test_execute_approved_intent_routes_live_crypto_to_alpaca(monkeypatch):
    settings = get_settings()
    old_enabled = settings.LIVE_TRADING_ENABLED
    old_key = settings.ALPACA_API_KEY
    old_secret = settings.ALPACA_SECRET_KEY
    old_base = settings.ALPACA_LIVE_BASE_URL
    settings.LIVE_TRADING_ENABLED = True
    settings.ALPACA_API_KEY = "alpaca-key"
    settings.ALPACA_SECRET_KEY = "alpaca-secret"
    settings.ALPACA_LIVE_BASE_URL = "https://example.alpaca"

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "alpaca-order-1",
                "symbol": "BTC/USD",
                "side": "buy",
                "qty": "0.01",
                "filled_avg_price": "64000.5",
                "status": "accepted",
                "created_at": "2026-04-21T22:40:00Z",
            }

    captured = {}

    def _post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        return _Resp()

    monkeypatch.setattr(execution_adapter_module.requests, "post", _post)
    try:
        result = execute_approved_intent(
            {
                "symbol": "BTC/USD",
                "side": "buy",
                "quantity": 0.01,
                "approved": True,
                "decision_id": "dec-live-crypto",
                "risk_id": "risk-live-crypto",
                "broker_mode": "live",
                "price": 64000.0,
                "asset_class": "crypto",
                "routing_mode": "paper_crypto",
                "instrument_type": "crypto_spot",
            },
            broker=_broker(),
        )
    finally:
        settings.LIVE_TRADING_ENABLED = old_enabled
        settings.ALPACA_API_KEY = old_key
        settings.ALPACA_SECRET_KEY = old_secret
        settings.ALPACA_LIVE_BASE_URL = old_base

    assert result["status"] == "executed"
    assert captured["url"] == "https://example.alpaca/v2/orders"
    assert captured["json"]["symbol"] == "BTC/USD"


def test_execute_approved_intent_routes_live_forex_to_oanda(monkeypatch):
    settings = get_settings()
    old_enabled = settings.LIVE_TRADING_ENABLED
    old_token = settings.OANDA_API_TOKEN
    old_account = settings.OANDA_ACCOUNT_ID
    old_base = settings.OANDA_LIVE_BASE_URL
    settings.LIVE_TRADING_ENABLED = True
    settings.OANDA_API_TOKEN = "oanda-token"
    settings.OANDA_ACCOUNT_ID = "acct-1"
    settings.OANDA_LIVE_BASE_URL = "https://example.oanda"

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "lastTransactionID": "1001",
                "orderFillTransaction": {
                    "id": "1001",
                    "time": "2026-04-21T22:41:00Z",
                    "price": "1.0825",
                    "units": "1000",
                },
            }

    captured = {}

    def _post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        return _Resp()

    monkeypatch.setattr(execution_adapter_module.requests, "post", _post)
    try:
        result = execute_approved_intent(
            {
                "symbol": "EUR/USD",
                "side": "buy",
                "quantity": 1000,
                "approved": True,
                "decision_id": "dec-live-fx",
                "risk_id": "risk-live-fx",
                "broker_mode": "live",
                "price": 1.082,
                "asset_class": "forex",
                "routing_mode": "paper_forex",
                "instrument_type": "fx_spot",
            },
            broker=_broker(),
        )
    finally:
        settings.LIVE_TRADING_ENABLED = old_enabled
        settings.OANDA_API_TOKEN = old_token
        settings.OANDA_ACCOUNT_ID = old_account
        settings.OANDA_LIVE_BASE_URL = old_base

    assert result["status"] == "executed"
    assert captured["url"] == "https://example.oanda/v3/accounts/acct-1/orders"
    assert captured["json"]["order"]["instrument"] == "EUR_USD"
