"""
Voice input route — transcribe audio via OpenAI Whisper, then process as text.

Flow: User records audio → POST /voice/transcribe → Whisper → text
      Text is then sent through the same pipeline as chat messages.
"""

import logging
import tempfile

from fastapi import APIRouter, UploadFile, File, Form
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    session_id: str = Form(...),
):
    """
    Transcribe audio file using OpenAI Whisper API.

    Accepts any audio format (mp3, wav, webm, m4a, etc.)
    Returns the transcribed text and processes it through the agent pipeline.
    """
    if not settings.OPENAI_API_KEY:
        return {"error": "OPENAI_API_KEY not set", "status": "error"}

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        # Save uploaded audio to temp file
        with tempfile.NamedTemporaryFile(suffix=f".{audio.filename.split('.')[-1]}", delete=False) as tmp:
            content = await audio.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Transcribe with Whisper
        with open(tmp_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model=settings.WHISPER_MODEL,
                file=audio_file,
            )

        transcribed_text = transcript.text
        logger.info(f"[voice] Transcribed: '{transcribed_text[:80]}' (session: {session_id})")

        # Process through the same pipeline as chat
        from app.workers.webhook_worker import _handle_user_spoke

        result = await _handle_user_spoke({
            "call_id": session_id,
            "text": transcribed_text,
            "caller_id": "voice_user",
        })

        return {
            "transcription": transcribed_text,
            "response": result.get("response", ""),
            "role": result.get("role"),
            "state": result.get("state"),
            "sentiment": result.get("sentiment", {}).get("sentiment"),
            "status": "ok",
        }

    except Exception as e:
        logger.error(f"[voice] Transcription failed: {e}")
        return {"error": str(e), "status": "error"}
