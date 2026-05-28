#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timedelta
import json

db = sqlite3.connect('trading_bot.db')
db.row_factory = sqlite3.Row
cursor = db.cursor()

print("=" * 90)
print("VEKTOR APP AUDIT REPORT".center(90))
print("=" * 90)

# 1. TRADE EXECUTION QUALITY
print("\n1. TRADE EXECUTION QUALITY")
print("-" * 90)
cursor.execute('SELECT COUNT(*) as total FROM orders')
total_orders = cursor.fetchone()['total']
print(f"Total Orders Executed: {total_orders}")

cursor.execute('SELECT AVG(pnl) as avg_pnl FROM orders WHERE pnl IS NOT NULL')
avg_pnl = cursor.fetchone()['avg_pnl']
print(f"Average PnL per Trade: ${avg_pnl:.2f}" if avg_pnl else "Average PnL: N/A")

cursor.execute('SELECT SUM(pnl) as total_pnl FROM orders WHERE pnl IS NOT NULL')
total_pnl = cursor.fetchone()['total_pnl']
print(f"Total PnL: ${total_pnl:.2f}" if total_pnl else "Total PnL: $0")

# Win rate
cursor.execute('SELECT COUNT(*) as wins FROM orders WHERE pnl > 0')
wins = cursor.fetchone()['wins']
win_rate = (wins / total_orders * 100) if total_orders > 0 else 0
print(f"Win Rate: {win_rate:.1f}% ({wins}/{total_orders} trades)")

# 2. DECISION QUALITY
print("\n2. DECISION PIPELINE QUALITY")
print("-" * 90)
cursor.execute('SELECT COUNT(*) as total FROM decisions')
total_decisions = cursor.fetchone()['total']
print(f"Total Decisions Generated: {total_decisions}")

cursor.execute("SELECT COUNT(*) as count FROM decisions WHERE status = 'approved'")
approved = cursor.fetchone()['count']
print(f"Approved: {approved}")

cursor.execute("SELECT COUNT(*) as count FROM decisions WHERE status = 'rejected'")
rejected = cursor.fetchone()['count']
print(f"Rejected/Blocked: {rejected}")

approval_rate = (approved / total_decisions * 100) if total_decisions > 0 else 0
print(f"Approval Rate: {approval_rate:.1f}%")

# 3. DATA PIPELINE HEALTH
print("\n3. DATA PIPELINE HEALTH")
print("-" * 90)
cursor.execute('SELECT COUNT(*) as total FROM data_raw_events')
raw_events = cursor.fetchone()['total']
print(f"Raw Data Events Ingested: {raw_events}")

cursor.execute('SELECT COUNT(*) as total FROM data_quality_events')
quality_events = cursor.fetchone()['total']
print(f"Quality Checks Performed: {quality_events}")

cursor.execute('''
SELECT asset_class, COUNT(*) as count 
FROM data_raw_events 
GROUP BY asset_class
''')
by_asset = cursor.fetchall()
print("Data by Asset Class:")
for row in by_asset:
    print(f"  {row['asset_class']}: {row['count']} events")

cursor.execute('''
SELECT AVG(score) as avg_score FROM data_quality_events
''')
avg_quality = cursor.fetchone()['avg_score']
print(f"Average Data Quality Score: {avg_quality:.2f}/1.0" if avg_quality else "Quality: N/A")

# 4. RISK ENFORCEMENT
print("\n4. RISK & COMPLIANCE")
print("-" * 90)
cursor.execute('SELECT COUNT(*) as total FROM audit_log')
audit_events = cursor.fetchone()['total']
print(f"Audit Log Events: {audit_events}")

cursor.execute("SELECT COUNT(*) as blocked FROM audit_log WHERE event_type = 'policy_blocked'")
blocked = cursor.fetchone()['blocked']
print(f"Blocked Trades (Policy): {blocked}")

cursor.execute('SELECT * FROM broker_state ORDER BY updated_at DESC LIMIT 1')
broker = cursor.fetchone()
if broker:
    print(f"Cash Available: ${broker['cash']:.2f}")
    print(f"Total Positions: {broker['position_count']}")

# 5. KNOWLEDGE PERSISTENCE
print("\n5. KNOWLEDGE GRAPH & MEMORY")
print("-" * 90)
cursor.execute('SELECT COUNT(*) as total FROM research_reports')
reports = cursor.fetchone()['total']
print(f"Research Reports Stored: {reports}")

cursor.execute('SELECT COUNT(*) as total FROM sentiment_snapshots')
sentiments = cursor.fetchone()['total']
print(f"Sentiment Snapshots: {sentiments}")

cursor.execute('SELECT COUNT(*) as total FROM decisions')
indexed_decisions = cursor.fetchone()['total']
print(f"Indexed Decisions: {indexed_decisions}")

# 6. ALGORITHMIC SIGNAL QUALITY
print("\n6. SIGNAL GENERATION")
print("-" * 90)
cursor.execute('''
SELECT symbol, COUNT(*) as signals 
FROM decisions 
WHERE status = 'approved'
GROUP BY symbol
''')
signals_by_symbol = cursor.fetchall()
print("Signal Generation by Symbol:")
for row in signals_by_symbol:
    print(f"  {row['symbol']}: {row['signals']} approved signals")

# 7. MODEL PERFORMANCE
print("\n7. MODEL & FEATURE ENGINEERING")
print("-" * 90)
cursor.execute('SELECT COUNT(*) as total FROM data_quality_events WHERE severity = "error"')
quality_errors = cursor.fetchone()['total']
print(f"Data Quality Errors: {quality_errors}")

cursor.execute('''
SELECT provider, COUNT(*) as count 
FROM data_raw_events 
GROUP BY provider
''')
by_provider = cursor.fetchall()
print("Data Sources Contributing:")
for row in by_provider:
    print(f"  {row['provider']}: {row['count']} events")

# 8. SUMMARY METRICS
print("\n8. SYSTEM HEALTH SUMMARY")
print("-" * 90)
uptime_ok = raw_events > 100
decision_flow_ok = total_decisions > 0
trade_execution_ok = total_orders > 0
quality_ok = avg_quality > 0.75 if avg_quality else False
memory_ok = reports > 0 and indexed_decisions > 0

print(f"Data Ingestion: {'✓' if uptime_ok else '✗'} ({raw_events} events)")
print(f"Decision Pipeline: {'✓' if decision_flow_ok else '✗'} ({total_decisions} decisions)")
print(f"Trade Execution: {'✓' if trade_execution_ok else '✗'} ({total_orders} trades)")
print(f"Data Quality: {'✓' if quality_ok else '✗'} (avg score: {avg_quality:.2f})")
print(f"Memory/Persistence: {'✓' if memory_ok else '✗'} ({reports} reports)")

db.close()
