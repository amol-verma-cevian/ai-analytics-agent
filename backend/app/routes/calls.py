from fastapi import APIRouter, Query
from typing import Optional

from app.models.database import get_connection

router = APIRouter()


@router.get("/")
async def list_calls(
    role: Optional[str] = None,
    limit: int = Query(default=50, le=200),
):
    """List call history, optionally filtered by role."""
    conn = get_connection()
    query = "SELECT * FROM calls WHERE 1=1"
    params = []

    if role:
        query += " AND role_detected = ?"
        params.append(role)

    query += " ORDER BY started_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@router.get("/{call_id}")
async def get_call(call_id: str):
    """Get a specific call with its evaluations."""
    conn = get_connection()

    call = conn.execute("SELECT * FROM calls WHERE call_id = ?", (call_id,)).fetchone()
    if not call:
        conn.close()
        return {"error": "Call not found"}

    evals = conn.execute(
        "SELECT * FROM evaluations WHERE call_id = ? ORDER BY turn_number", (call_id,)
    ).fetchall()

    conn.close()
    return {
        "call": dict(call),
        "evaluations": [dict(e) for e in evals],
    }
