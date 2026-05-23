param([string]$Db='backend/trading_bot.db',[switch]$SkipPytest)
$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH='backend';$env:TEMP='C:\tmp';$env:TMP='C:\tmp';$env:SQLITE_PATH=$Db
New-Item -ItemType Directory -Force -Path 'C:\tmp\tradingbot-pytest-cache' | Out-Null
if(-not $SkipPytest){py -3 -m pytest backend\tests\test_data_pipeline.py -q -o cache_dir=C:\tmp\tradingbot-pytest-cache;py -3 -m pytest backend\tests\test_quant_regime.py backend\tests\test_signals.py -q -o cache_dir=C:\tmp\tradingbot-pytest-cache}
@'
import json, os, sqlite3, pandas as pd
from pathlib import Path
from app.ml.alpha_model import ensure_model, model_status, predict
p=Path(os.environ['SQLITE_PATH'])
c=sqlite3.connect(p); c.row_factory=sqlite3.Row; cur=c.cursor()
counts={}
for t in ['data_raw_events','data_market_prices','data_market_quotes','data_market_bars','data_text_events','data_fundamentals','data_feature_vectors','data_quality_events','data_provider_health','data_snapshots','data_pipeline_runs','positions','orders','cash_snapshots','fund_performance_snapshots']:
    cur.execute(f'SELECT COUNT(*) c FROM {t}'); counts[t]=cur.fetchone()['c']
cur.execute('SELECT symbol,use_case,category,score,created_at FROM data_feature_vectors ORDER BY created_at DESC LIMIT 10')
before=model_status(); ensure_model(); after=model_status(); rows=[]
for i in range(80):
    px=100+i*0.4; rows.append({'ts':pd.Timestamp('2026-01-01')+pd.Timedelta(days=i),'open':px-0.3,'high':px+0.8,'low':px-0.8,'close':px,'volume':1000000+i*5000})
out={'db':str(p.resolve()),'size_mb':round(p.stat().st_size/1024/1024,2),'counts':counts,'latest_features':[dict(x) for x in cur.fetchall()],'model_before':before,'model_after':after,'synthetic_alpha':predict(pd.DataFrame(rows))}
try:
    from app.backtest.engine import run_backtest
    r=run_backtest('AAPL',period='1y',benchmark='SPY'); out['backtest_aapl']={'metrics':r.metrics,'trade_count':len(r.trades)}
except Exception as e:
    out['backtest_aapl']={'error':str(e)}
print(json.dumps(out,indent=2,default=str))
'@ | py -3 -
