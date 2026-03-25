from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.models.database import init_db
from app.models.seed_data import seed_all
from app.routes import health, webhook, metrics, calls, evaluation, voice


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on startup and shutdown."""
    # Startup: initialize DB and seed if empty
    init_db()
    from datetime import date
    from app.models.database import get_connection
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM cities").fetchone()[0]
    if count == 0:
        conn.close()
        seed_all()
        print(f"[startup] Database seeded (first run)")
    else:
        # Re-seed if data is stale (dates don't match today)
        latest = conn.execute("SELECT MAX(date) FROM orders").fetchone()[0]
        conn.close()
        if latest != date.today().isoformat():
            seed_all()
            print(f"[startup] Database re-seeded (data was stale: {latest})")
        else:
            print(f"[startup] Database ready (data is fresh)")

    yield

    # Shutdown: cleanup
    print(f"[shutdown] Server stopping")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

# CORS — allows frontend (React) to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health.router, tags=["Health"])
app.include_router(webhook.router, prefix="/webhook", tags=["Webhook"])
app.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])
app.include_router(calls.router, prefix="/calls", tags=["Calls"])
app.include_router(evaluation.router, prefix="/evaluations", tags=["Evaluations"])
app.include_router(voice.router, prefix="/voice", tags=["Voice"])


# --- WebSocket endpoint ---
from app.services.ws_manager import manager


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Dashboard connects here for live updates.

    Events pushed to clients:
    - call_started:       new session started
    - call_ended:         session finished
    - user_spoke:         user said something (includes response)
    - anomaly_detected:   pre-briefing scan found something
    - evaluation_scored:  7-dimension score for a turn
    - metric_update:      business metric changed
    - sentiment_changed:  user sentiment shifted
    - escalation:         session escalated to human
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# --- Direct Chat Endpoint (no Redis needed) ---
from fastapi import Body
from app.workers.webhook_worker import _handle_user_spoke, _handle_call_started, _handle_call_ended
import uuid


@app.post("/chat/start")
async def chat_start():
    """Start a new chat session — returns a session_id."""
    session_id = str(uuid.uuid4())[:12]
    result = await _handle_call_started({
        "call_id": session_id,
        "caller_id": "chat_user",
    })
    return {"session_id": session_id, "status": result["status"]}


@app.post("/chat/message")
async def chat_message(
    session_id: str = Body(...),
    text: str = Body(...),
):
    """Send a message in a chat session — returns the agent's response."""
    result = await _handle_user_spoke({
        "call_id": session_id,
        "text": text,
        "caller_id": "chat_user",
    })
    return {
        "response": result.get("response", ""),
        "role": result.get("role"),
        "state": result.get("state"),
        "sentiment": result.get("sentiment", {}).get("sentiment"),
        "tool_calls": len(result.get("tool_calls", [])),
        "latency_ms": result.get("latency_ms", 0),
    }


@app.post("/chat/end")
async def chat_end(session_id: str = Body(..., embed=True)):
    """End a chat session."""
    result = await _handle_call_ended({"call_id": session_id})
    return {"status": result["status"]}


# --- Serve React frontend (production) ---
STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="static-assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """Serve the React SPA for any non-API route."""
        file = STATIC_DIR / path
        if file.exists() and file.is_file():
            return FileResponse(file)
        return FileResponse(STATIC_DIR / "index.html")
