# Step 5 — WebSocket Setup

## What this component does
Creates a persistent live connection between the backend and dashboard. Instead of the dashboard polling "anything new?" every second, the server pushes updates instantly — call started, anomaly detected, evaluation scored.

## Why WebSocket over polling

```
Polling (bad for us):
Dashboard: "Any updates?"     → Server: "No"       (wasted request)
Dashboard: "Any updates?"     → Server: "No"       (wasted request)
Dashboard: "Any updates?"     → Server: "Yes!"     (up to 1 sec delay)

WebSocket (what we use):
Dashboard ←→ Server: persistent connection
Server: "Call started!"       → Dashboard updates instantly (0ms delay)
Server: "Anomaly detected!"   → Dashboard updates instantly
```

Think of it like this:
- **Polling** = calling your friend every minute asking "are you here yet?"
- **WebSocket** = your friend texts you when they arrive

## How it connects to the rest
- ARQ worker (Step 4) calls `manager.broadcast()` after processing each event
- React dashboard (Step 19) connects on page load via `useWebSocket.js`
- Every service that produces user-visible data goes through this

## Production reality (Swiggy connection)
Swiggy's Databricks article: "real-time granular tracing to track each step of the Agent" and "real-time observability from Model Serving." Their monitoring feeds metrics into a centralized system in real-time. Our WebSocket is the transport layer for that same pattern.

---

## Architecture

```
┌──────────────┐     ┌───────────────────┐     ┌──────────────────┐
│  ARQ Worker  │     │  ConnectionManager │     │  Dashboard (React)│
│              │     │                   │     │                  │
│ Processes    │────>│ broadcast()       │────>│ useWebSocket.js  │
│ webhook job  │     │                   │     │ Updates panels   │
│              │     │ Tracks all        │     │                  │
│              │     │ connected clients │     │                  │
└──────────────┘     └───────────────────┘     └──────────────────┘
                            │
                            │ (can have multiple dashboards)
                            │
                     ┌──────────────────┐
                     │  Dashboard #2    │
                     │  (CEO's screen)  │
                     └──────────────────┘
```

## Events Broadcast to Dashboard

| Event | When | Data included |
|-------|------|--------------|
| `call_started` | New call comes in | call_id, caller_id, state |
| `user_spoke` | User says something | call_id, user_text, agent_response, turn |
| `call_ended` | Call finishes | call_id, timestamp |
| `anomaly_detected` | Pre-briefing scan finds issue | metric, city, deviation_pct, severity |
| `evaluation_scored` | 7-dim score computed | call_id, scores, turn_number |
| `metric_update` | Business metric changes | metric_name, value |
| `sentiment_changed` | User mood shifts | call_id, old_sentiment, new_sentiment |
| `escalation` | Call escalated to human | call_id, reason |

---

## Key Files

### `ws_manager.py` — Connection Manager
- **Why a class?** Multiple dashboards can connect (CEO on one screen, Ops on another). We need to track them all and handle disconnects gracefully.
- `connect()` — accepts new WebSocket, adds to list
- `disconnect()` — removes from list when browser closes
- `broadcast()` — sends event to ALL connected dashboards
- `send_to_one()` — sends to a specific dashboard (e.g., initial state on connect)
- Dead connections are automatically cleaned up during broadcast

### `main.py` — WebSocket endpoint added
- `@app.websocket("/ws")` — dashboard connects here
- Keeps connection alive by listening in a loop
- On disconnect, cleans up via manager

### `webhook_worker.py` — Now broadcasts events
- `_handle_call_started()` → broadcasts `call_started`
- `_handle_user_spoke()` → broadcasts `user_spoke` with response
- `_handle_call_ended()` → broadcasts `call_ended`

---

## How the Frontend Will Use It (Step 19 preview)

```javascript
// React hook — connects once, receives all events
const useWebSocket = () => {
  const [events, setEvents] = useState([]);

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws');
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      // data = { type: "call_started", data: { call_id: "...", ... } }
      setEvents(prev => [data, ...prev]);
    };
    return () => ws.close();
  }, []);

  return events;
};
```

Each dashboard panel filters events by type:
- LiveMetrics panel listens for `metric_update`
- CallHistory panel listens for `call_started`, `call_ended`
- AnomalyFeed panel listens for `anomaly_detected`
- EvalRadar panel listens for `evaluation_scored`

---

## Test Results

```
WebSocket connection: OPEN (accepted by server)
WebSocket close: clean disconnect
Manager broadcast with 0 connections: silently skipped (no crash)
```

## What breaks if we remove it

| If you remove... | What breaks |
|-----------------|-------------|
| WebSocket endpoint | Dashboard has no live data. Must refresh page manually. |
| ConnectionManager | No way to track who's connected. Broadcasts fail. |
| broadcast() calls in worker | Worker processes fine but dashboard never updates. |
| Dead connection cleanup | Memory leak — disconnected clients pile up. |

## Where we simplified vs production

| Us | Production |
|---|---|
| Single WebSocket on one server | WebSocket through load balancer (sticky sessions / Redis pub-sub) |
| All events to all clients | Per-user event filtering (CEO sees different events than Ops) |
| No authentication on WebSocket | Token-based auth on connection |
| In-memory connection list | Redis pub-sub for multi-server broadcast |
| No reconnection logic (yet) | Auto-reconnect with exponential backoff |

---

## Interview questions

### "Why WebSocket instead of Server-Sent Events (SSE)?"
**Answer**: "WebSocket is bidirectional — the dashboard can send messages back (like filter preferences or acknowledgements). SSE is one-way only. Also, FastAPI has built-in WebSocket support, while SSE needs extra middleware. For a real-time dashboard where we might add interactive features later, WebSocket is more flexible."

### "How do you handle multiple dashboards?"
**Answer**: "The ConnectionManager maintains a list of all active WebSocket connections. When any event happens, broadcast() iterates through all connections and sends the same event. If a connection is dead (browser closed), it's automatically removed during the next broadcast attempt."

### "What design patterns did you use?"
**Answer**: "The WebSocket layer uses the Observer pattern. The ConnectionManager is the subject — it maintains a list of subscribed dashboard clients. When the ARQ worker processes an event, it calls broadcast(), which notifies all observers. This decouples the event producer (worker) from the consumers (dashboards). Adding a new consumer — like a Slack bot — means just subscribing another observer, zero changes to the worker."

### "What happens if the dashboard disconnects and reconnects?"
**Answer**: "Right now, they'd miss events that happened while disconnected. In production, you'd solve this with: (1) a reconnection buffer that replays recent events, or (2) the dashboard fetching the latest state via REST API on reconnect, then switching to WebSocket for live updates. We do the REST fallback approach — the dashboard loads initial state from /metrics/* and /calls/*, then WebSocket handles updates."
