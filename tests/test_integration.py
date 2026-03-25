"""
Integration Test Suite — End-to-End Pipeline Verification.

Tests the complete flow from API request through all pipeline stages.
Run with: python3 tests/test_integration.py

IMPORTANT: Requires the backend to be running (uvicorn on port 8000).
Tests that call the LLM require OPENAI_API_KEY to be set.
"""

import asyncio
import json
import sys
import time
import httpx

BASE = "http://localhost:8000"

PASS = 0
FAIL = 0
SKIP = 0


def log(status, test_name, detail=""):
    global PASS, FAIL, SKIP
    icons = {"PASS": "[OK]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}
    print(f"  {icons[status]} {test_name}" + (f" — {detail}" if detail else ""))
    if status == "PASS":
        PASS += 1
    elif status == "FAIL":
        FAIL += 1
    else:
        SKIP += 1


async def run_tests():
    global PASS, FAIL, SKIP

    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as c:

        # ── 1. Health Check ──
        print("\n1. Health & Infrastructure")
        try:
            r = await c.get("/health")
            data = r.json()
            assert data["status"] == "healthy"
            assert data["database"] == "connected"
            log("PASS", "Health endpoint", f"v{data['version']}")
        except Exception as e:
            log("FAIL", "Health endpoint", str(e))
            print("\n  Backend not running! Start with: cd backend && python3 -m uvicorn app.main:app")
            return

        # ── 2. Data APIs ──
        print("\n2. Data API Endpoints")

        for name, path in [
            ("Orders", "/metrics/orders"),
            ("Revenue", "/metrics/revenue"),
            ("Cancellations", "/metrics/cancellations"),
            ("Cities", "/metrics/cities"),
            ("Restaurants", "/metrics/restaurants"),
            ("Hourly trends", "/metrics/hourly"),
            ("CEO summary", "/metrics/ceo-summary"),
            ("Week comparison", "/metrics/week-comparison"),
        ]:
            try:
                r = await c.get(path)
                assert r.status_code == 200
                data = r.json()
                assert data is not None
                log("PASS", name, f"{len(data) if isinstance(data, list) else 'dict'} returned")
            except Exception as e:
                log("FAIL", name, str(e))

        # ── 3. System APIs ──
        print("\n3. System Endpoints")

        for name, path in [
            ("Call history", "/calls/"),
            ("Evaluations", "/evaluations/"),
            ("AB results", "/evaluations/ab-results"),
            ("Anomalies", "/evaluations/anomalies"),
            ("Escalations", "/evaluations/escalations"),
            ("Prompt registry", "/evaluations/prompts"),
        ]:
            try:
                r = await c.get(path)
                assert r.status_code == 200
                log("PASS", name)
            except Exception as e:
                log("FAIL", name, str(e))

        # ── 4. Chat Flow (Full Pipeline) ──
        print("\n4. Chat Pipeline (End-to-End)")

        # Start session
        try:
            r = await c.post("/chat/start")
            assert r.status_code == 200
            session = r.json()
            sid = session["session_id"]
            log("PASS", "Chat start", f"session={sid}")
        except Exception as e:
            log("FAIL", "Chat start", str(e))
            sid = None

        if sid:
            # Send message — role detection (first message advances from GREETING)
            try:
                r = await c.post("/chat/message", json={"session_id": sid, "text": "I am the CEO"})
                assert r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}"
                data = r.json()
                assert "response" in data, f"missing response key, got: {list(data.keys())}"
                assert len(data.get("response", "")) > 5, f"response too short: '{data.get('response', '')}'"
                log("PASS", "First message", f"role={data.get('role')}, state={data.get('state')}, {len(data['response'])} chars")
            except Exception as e:
                log("FAIL", "First message", str(e))

            # Send follow-up — drill down
            try:
                r = await c.post("/chat/message", json={"session_id": sid, "text": "What about Mumbai?"})
                assert r.status_code == 200
                data = r.json()
                assert data["response"]
                log("PASS", "Drill down", f"tools={data.get('tool_calls', 0)}, latency={data.get('latency_ms', 0)}ms")
            except Exception as e:
                log("FAIL", "Drill down", str(e))

            # End session
            try:
                r = await c.post("/chat/end", json={"session_id": sid})
                assert r.status_code == 200
                log("PASS", "Chat end")
            except Exception as e:
                log("FAIL", "Chat end", str(e))

        # ── 5. Prompt Registry ──
        print("\n5. Prompt Registry")

        try:
            r = await c.get("/evaluations/prompts")
            prompts = r.json()
            assert "ceo" in prompts
            assert "ops_manager" in prompts
            assert "analyst" in prompts
            log("PASS", "List all prompts", f"{len(prompts)} roles")
        except Exception as e:
            log("FAIL", "List all prompts", str(e))

        try:
            r = await c.get("/evaluations/prompts/ceo")
            prompt = r.json()
            assert "style_note" in prompt
            log("PASS", "Get CEO prompt", f"word_limit={prompt.get('word_limit')}")
        except Exception as e:
            log("FAIL", "Get CEO prompt", str(e))

        # ── 6. Voice Endpoint (dry run) ──
        print("\n6. Voice Endpoint")
        log("SKIP", "Whisper transcription", "No audio file for test — endpoint exists at /voice/transcribe")

        # ── 7. Anomaly Detection ──
        print("\n7. Anomaly Detection")
        try:
            r = await c.get("/evaluations/anomalies")
            anomalies = r.json()
            if len(anomalies) > 0:
                a = anomalies[0]
                assert "severity" in a
                assert "metric" in a
                log("PASS", "Anomaly data", f"{len(anomalies)} anomalies, top: {a['severity']} {a['metric']}")
            else:
                log("PASS", "Anomaly data", "0 anomalies (clean)")
        except Exception as e:
            log("FAIL", "Anomaly data", str(e))

    # ── Summary ──
    print(f"\n{'='*50}")
    print(f"  Results: {PASS} passed, {FAIL} failed, {SKIP} skipped")
    print(f"{'='*50}")

    return FAIL == 0


if __name__ == "__main__":
    print("=" * 50)
    print("  AI Analytics Briefing Agent — Integration Tests")
    print("=" * 50)

    start = time.time()
    success = asyncio.run(run_tests())
    elapsed = time.time() - start

    print(f"\n  Completed in {elapsed:.1f}s")

    if not success:
        sys.exit(1)
