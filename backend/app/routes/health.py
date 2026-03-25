from fastapi import APIRouter
from app.models.database import get_connection

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check — Railway/load balancers hit this to know we're alive."""
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "status": "healthy",
        "database": db_status,
        "version": "1.0.0",
    }
