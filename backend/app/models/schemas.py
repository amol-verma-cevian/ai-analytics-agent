from pydantic import BaseModel
from typing import Optional


# --- Webhook payloads ---

class WebhookPayload(BaseModel):
    call_id: str
    event: str  # call_started, user_spoke, call_ended, silence_detected
    caller_id: Optional[str] = None
    text: Optional[str] = None
    metadata: Optional[dict] = None


class WebhookResponse(BaseModel):
    status: str
    message: Optional[str] = None


# --- Metrics responses ---

class OrderSummary(BaseModel):
    date: str
    city: str
    total_orders: int
    delivered: int
    avg_delivery_time_mins: float


class RevenueSummary(BaseModel):
    date: str
    city: str
    gross_revenue: float
    net_revenue: float
    avg_order_value: float


class CancellationSummary(BaseModel):
    date: str
    city: str
    total_cancellations: int
    reason: str
    cancellation_rate: float


class RestaurantInfo(BaseModel):
    name: str
    city: str
    cuisine: str
    avg_rating: float
    complaints_last_7d: int
    avg_prep_time_mins: float


# --- Call and evaluation ---

class CallRecord(BaseModel):
    call_id: str
    direction: str
    role_detected: Optional[str] = None
    state: str
    sentiment: str
    escalated: bool
    prompt_version: Optional[str] = None
    total_turns: int
    started_at: str
    ended_at: Optional[str] = None
    summary: Optional[str] = None
    whatsapp_sent: bool


class EvaluationScore(BaseModel):
    call_id: str
    turn_number: int
    accuracy: int
    factual_correctness: int
    stability: int
    response_style: int
    conversational_coherence: int
    token_count: int
    latency_ms: int
    prompt_version: Optional[str] = None


class AnomalyRecord(BaseModel):
    metric: str
    city: Optional[str] = None
    current_value: float
    baseline_value: float
    deviation_pct: float
    severity: str


class ManagerInfo(BaseModel):
    name: str
    role: str
    email: str
    phone: str
    whatsapp: str
    preferred_briefing_time: str
