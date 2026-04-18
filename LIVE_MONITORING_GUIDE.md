# 🎯 Live Backend Monitoring - Complete Guide

Your backend is now fully instrumented with real-time monitoring. Here's everything you can see live:

## 🔴 **IMPORTANT: Restart Backend to See Changes**

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

When you start, you'll see detailed console output showing every component initializing.

---

## 📊 **Console Output (What You'll See on Startup)**

```
================================================================================
🚀 ALFRED STARTUP SEQUENCE 5.1.0
================================================================================
⏰ Timestamp: 2026-04-17T12:30:45.123456Z
🌍 Environment: dev
🤖 Agent Runtime: ENABLED
📊 Auto Trading: DISABLED
--------------------------------------------------------------------------------
✅ Database                        OK         trading_bot.db initialized
✅ OpenClaw Adapter               OK         Event sink configured
✅ Broker State                   OK         Restored: cash=$20.52
✅ Market Data Stream             OK         WebSocket loop started
✅ Auto Trader                    OK         Disabled (manual trading mode)
✅ Agent Runtime                  OK         Fund agent runtime started
✅ Alpha Model                    OK         LightGBM model loaded
✅ Sentiment Model                OK         FinBERT loaded
================================================================================
📈 FUND SYSTEM STATISTICS
================================================================================
🎯 Active Tasks: 5
📋 Pending Decisions: 2
📚 Knowledge Events: 156
🏷️  Knowledge Entities: 89
💰 Broker Cash: $20.52
📊 Portfolio Equity: $1,000,000.00
📍 Positions: 5

🔄 Recent Active Tasks:
   └─ research_analysis [running] - 5a6b7c8d9e0f...
   └─ risk_assessment [pending] - 1f2g3h4i5j6k...
   └─ trade_execution [queued] - 9z8y7x6w5v4u...

⏳ Pending Decisions:
   └─ sleeve_allocation - 4a5b6c7d8e9f...
   └─ trade_approval - 2z3y4x5w6v7u...
================================================================================
✅ ALFRED READY - All systems operational
```

---

## 🌐 **Live Monitoring Endpoints**

Access these from your browser or API client while the backend is running on port 8000.

### **1. Complete System Status** (All-in-one dashboard)
```
GET http://localhost:8000/monitor/status
```
Shows everything: agents, tasks, decisions, broker, risk, realtime subscribers

**Response includes:**
- Fund system: agent runtime, orchestrator, knowledge graph, decision ledger
- Broker: cash, equity, positions
- Realtime stream: subscriber count
- Sample of active tasks and pending decisions

---

### **2. Detailed Health Check** (Most comprehensive)
```
GET http://localhost:8000/monitor/health-detailed
```
Shows complete system status + all components

**Additional data:**
- ML model status
- Sentiment model status
- Risk engine status
- WebSocket clients connected
- Market data watchlist

---

### **3. Active Tasks** (See what agents are working on)
```
GET http://localhost:8000/monitor/tasks
```
Returns all active fund tasks currently running

**Example:**
```json
{
  "count": 5,
  "tasks": [
    {
      "id": "task_123456",
      "type": "research_analysis",
      "status": "running",
      "created_at": "2026-04-17T12:30:45"
    },
    ...
  ]
}
```

---

### **4. Pending Decisions** (What's awaiting approval)
```
GET http://localhost:8000/monitor/decisions
```
Returns all pending decisions awaiting approval/rejection

**Example:**
```json
{
  "count": 2,
  "decisions": [
    {
      "id": "decision_789",
      "type": "sleeve_allocation",
      "status": "pending",
      "created_at": "2026-04-17T12:30:45"
    },
    ...
  ]
}
```

---

### **5. Knowledge Graph Stats** (Research & insights)
```
GET http://localhost:8000/monitor/knowledge
```
Shows what the fund has learned and recent events

**Returns:**
- Event count (total research events captured)
- Entity count (total entities discovered)
- Recent events (last 5)

---

### **6. Broker Status** (Trading positions)
```
GET http://localhost:8000/monitor/broker
```
Live trading account status with all positions

**Example:**
```json
{
  "cash": 20.52,
  "portfolio_value": 1000000.00,
  "positions_count": 5,
  "positions": [
    {
      "symbol": "META",
      "quantity": 100,
      "entry_price": 450.00,
      "current_price": 455.00,
      "unrealized_pnl": 500.00
    },
    ...
  ],
  "orders_count": 3
}
```

---

### **7. Agent Runtime Status** (Just agents)
```
GET http://localhost:8000/monitor/agents
```
Simple status of agent runtime

---

### **8. Original Health Endpoint** (Still works!)
```
GET http://localhost:8000/health
```
Classic health check maintained for backward compatibility

---

## 📈 **Sample Monitoring URLs to Try**

Open these in your browser or terminal while backend is running:

```
# Full dashboard snapshot
http://localhost:8000/monitor/status

# Most detailed check
http://localhost:8000/monitor/health-detailed

# What agents are doing
http://localhost:8000/monitor/tasks

# What needs approval
http://localhost:8000/monitor/decisions

# What the fund has learned
http://localhost:8000/monitor/knowledge

# Trading positions
http://localhost:8000/monitor/broker

# Classic health check
http://localhost:8000/health
```

---

## 🎨 **Building a Live Dashboard**

Want to see all this in one place? You can use the frontend! Here's what to add:

### Create `frontend/src/pages/Monitor.jsx`

```jsx
import React, { useState, useEffect } from 'react';

export default function Monitor() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await fetch('http://localhost:8000/monitor/status');
        const data = await response.json();
        setStatus(data);
      } catch (error) {
        console.error('Failed to fetch status:', error);
      }
      setLoading(false);
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 5000); // Update every 5s
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div>Loading...</div>;
  if (!status) return <div>Error loading status</div>;

  return (
    <div style={{ padding: '20px', fontFamily: 'monospace' }}>
      <h1>📊 Live Backend Monitor</h1>
      <pre>{JSON.stringify(status, null, 2)}</pre>
    </div>
  );
}
```

Then add to `frontend/src/App.jsx`:
```jsx
<Route path="/monitor" element={<Monitor />} />
```

Visit: `http://localhost:9000/monitor`

---

## 🚀 **Quick Commands**

### Watch Console Output (Windows PowerShell)
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

You'll see beautiful formatted output showing:
- ✅ All components starting up
- 📊 Fund statistics after startup
- 🔴 Any issues in red

### Check Status Every 5 Seconds (PowerShell)
```powershell
while($true) { 
    curl http://localhost:8000/monitor/status | jq '.fund.orchestrator'
    Start-Sleep -Seconds 5
}
```

### Watch Just Active Tasks (PowerShell)
```powershell
while($true) { 
    curl http://localhost:8000/monitor/tasks | jq '.'
    Start-Sleep -Seconds 5
}
```

### Watch Just Pending Decisions (PowerShell)
```powershell
while($true) { 
    curl http://localhost:8000/monitor/decisions | jq '.decisions'
    Start-Sleep -Seconds 5
}
```

---

## 📋 **What's Monitored**

### **Startup Checks**
- ✅ Database initialization
- ✅ Broker state restoration
- ✅ Market data stream (WebSocket)
- ✅ Auto-trader status
- ✅ Agent runtime startup
- ✅ ML model loading (LightGBM)
- ✅ Sentiment model loading (FinBERT)

### **Fund System**
- 🎯 Active research/analysis tasks
- 📋 Pending trade approvals
- 📚 Knowledge graph events captured
- 🏷️ Entities discovered
- 💰 Broker cash and positions

### **Component Health**
- Risk engine status
- ML model operational status
- Sentiment analysis ready
- WebSocket connections active
- Decision ledger operations

---

## 💡 **What You Should See**

**Good Signs:**
- ✅ All components show "OK"
- 📈 Active tasks > 0 (agents working)
- 📚 Knowledge events increasing (learning)
- 💰 Portfolio equity tracking correctly

**Bad Signs:**
- ❌ Components show "ERROR"
- 📋 Pending decisions stuck (approvals not happening)
- 🔴 Agent runtime not started when it should be

---

## 🔗 **Integration Points**

The monitoring system connects to:
- **Agent Runtime**: Shows if agents are running and working
- **Orchestrator**: Tracks active tasks and pending decisions
- **Knowledge Graph**: Monitors what the fund is learning
- **Broker**: Shows trading account status
- **Risk Engine**: Displays risk metrics
- **Realtime Stream**: Counts subscribers

Everything is live and updates as things happen!

---

## ✨ **Next Steps**

1. **Restart backend** to see the new monitoring in action
2. **Visit monitoring endpoints** in your browser
3. **Create a monitoring dashboard** on the frontend
4. **Set up alerts** for when things go wrong
5. **Log analysis** to `trading_bot.log` for detailed history

You now have complete visibility into everything happening in your trading bot! 🚀
