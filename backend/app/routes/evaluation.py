from fastapi import APIRouter, Query, Body
from typing import Optional

from app.models.database import get_connection
from app.services.prompt_registry import (
    get_all_prompts, get_prompt, promote_version, add_version, get_promotion_history
)

router = APIRouter()


@router.get("/")
async def list_evaluations(limit: int = Query(default=50, le=200)):
    """List recent evaluation scores."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM evaluations ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@router.get("/ab-results")
async def ab_test_results(role: Optional[str] = None):
    """Get A/B test results — average scores per prompt version per role."""
    conn = get_connection()
    query = """
        SELECT role, prompt_version,
               COUNT(*) as total_calls,
               ROUND(AVG(avg_score), 2) as mean_score
        FROM ab_test_results
    """
    params = []
    if role:
        query += " WHERE role = ?"
        params.append(role)

    query += " GROUP BY role, prompt_version ORDER BY role, prompt_version"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@router.get("/anomalies")
async def list_anomalies(acknowledged: Optional[bool] = None):
    """List detected anomalies."""
    conn = get_connection()
    query = "SELECT * FROM anomalies"
    params = []

    if acknowledged is not None:
        query += " WHERE acknowledged = ?"
        params.append(int(acknowledged))

    query += " ORDER BY detected_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@router.get("/escalations")
async def list_escalations(limit: int = Query(default=50, le=200)):
    """List recent escalations — fallback to human events."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM escalations ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# --- Prompt Registry Endpoints ---

@router.get("/prompts")
async def list_prompts():
    """Get all prompt versions for all roles."""
    return get_all_prompts()


@router.get("/prompts/{role}")
async def get_role_prompt(role: str, version: Optional[str] = None):
    """Get prompt config for a role (active version by default)."""
    return get_prompt(role, version)


@router.post("/prompts/{role}/promote")
async def promote_prompt(role: str, version: str = Body(..., embed=True)):
    """Promote a prompt version to active/production."""
    return promote_version(role, version)


@router.post("/prompts/{role}/add")
async def add_prompt_version(
    role: str,
    version_id: str = Body(...),
    style_note: str = Body(...),
    word_limit: Optional[int] = Body(None),
    description: str = Body(""),
):
    """Add a new prompt version for a role."""
    config = {
        "style_note": style_note,
        "word_limit": word_limit,
        "description": description,
    }
    return add_version(role, version_id, config)


@router.get("/prompts-history")
async def prompt_history(role: Optional[str] = None):
    """Get prompt promotion history (audit trail)."""
    return get_promotion_history(role)
