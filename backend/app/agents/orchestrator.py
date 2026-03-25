"""
Orchestrator Agent — the BRAIN of the system.

Implements a ReAct (Reasoning + Acting) loop using LLM tool use:
1. Receives user input + conversation context
2. LLM THINKS about what data it needs
3. LLM ACTS by calling tools (query data, search glossary)
4. LLM OBSERVES the results
5. Repeats until it has enough info
6. Generates a spoken response for the voice agent

Supports both OpenAI (function calling) and Anthropic (tool use).
Set LLM_PROVIDER in config to switch between them.

Swiggy connection:
- Hermes V3: "Agent layer that decides what actions to take — whether to
  clarify, rewrite, fetch metadata, or execute"
- Databricks article: tested ReAct, CoT, and Meta prompting.
  ReAct won for interactive flows.
"""

import json
import time
import logging
from typing import Optional

from app.config import settings
from app.services.data_service import (
    get_orders_summary, get_revenue_summary, get_cancellations_summary,
    get_restaurants, get_hourly_trends, get_week_comparison,
    get_top_metrics_for_ceo, get_city_info,
)
from app.rag.glossary import search_glossary
from app.rag.query_history import search_similar_queries
from app.services.anomaly_service import format_anomalies_for_agent
from app.services.freshness_service import format_freshness_for_agent

logger = logging.getLogger(__name__)

# --- Tool definitions in OPENAI format (function calling) ---

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_orders",
            "description": "Get order data (total orders, delivered, avg delivery time). Can filter by date and/or city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format. Defaults to yesterday."},
                    "city": {"type": "string", "description": "City name (Mumbai, Delhi, Bangalore, etc.)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_revenue",
            "description": "Get revenue data (gross, net, AOV). Can filter by date and/or city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format."},
                    "city": {"type": "string", "description": "City name."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cancellations",
            "description": "Get cancellation data (total, reason, rate). Can filter by date and/or city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format."},
                    "city": {"type": "string", "description": "City name."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_restaurants",
            "description": "Get restaurant performance data (rating, complaints, prep time). Can filter by city or minimum complaint count.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name."},
                    "min_complaints": {"type": "integer", "description": "Minimum complaint count to filter by."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hourly_trends",
            "description": "Get hourly order/revenue trends for a specific date and city. Shows lunch and dinner peaks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format."},
                    "city": {"type": "string", "description": "City name."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_week_comparison",
            "description": "Compare this week vs last week — total orders and percentage change. Can filter by city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name for comparison."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ceo_summary",
            "description": "Get top 3 metrics for CEO: total orders, total revenue, cancellation rate (yesterday, all cities).",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_city_info",
            "description": "Get city metadata: active restaurants, delivery partners, population tier.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name. Omit for all cities."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_glossary",
            "description": "Search business term definitions (AOV, GMV, CSAT, AHT, etc.). Use when user mentions a term you need to define or when you want to give accurate context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The term or concept to look up."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_past_queries",
            "description": "Search past similar queries and approaches used to answer them. Use to find proven patterns for common questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The user's question to find similar past queries for."},
                    "role": {"type": "string", "description": "User role: ceo, ops_manager, or analyst."},
                },
                "required": ["query"],
            },
        },
    },
]

# --- Anthropic format (kept for backwards compatibility) ---

ANTHROPIC_TOOLS = [
    {
        "name": tool["function"]["name"],
        "description": tool["function"]["description"],
        "input_schema": tool["function"]["parameters"],
    }
    for tool in OPENAI_TOOLS
]


def _execute_tool(name: str, args: dict) -> str:
    """Execute a tool call and return the result as a string."""
    try:
        if name == "get_orders":
            result = get_orders_summary(target_date=args.get("date"), city=args.get("city"))
        elif name == "get_revenue":
            result = get_revenue_summary(target_date=args.get("date"), city=args.get("city"))
        elif name == "get_cancellations":
            result = get_cancellations_summary(target_date=args.get("date"), city=args.get("city"))
        elif name == "get_restaurants":
            result = get_restaurants(city=args.get("city"), min_complaints=args.get("min_complaints"))
        elif name == "get_hourly_trends":
            result = get_hourly_trends(target_date=args.get("date"), city=args.get("city"))
        elif name == "get_week_comparison":
            result = get_week_comparison(city=args.get("city"))
        elif name == "get_ceo_summary":
            result = get_top_metrics_for_ceo()
        elif name == "get_city_info":
            result = get_city_info(city=args.get("city"))
        elif name == "search_glossary":
            result = search_glossary(args["query"])
        elif name == "search_past_queries":
            result = search_similar_queries(args["query"], role=args.get("role"))
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

        return json.dumps(result, default=str)
    except Exception as e:
        logger.error(f"[orchestrator] Tool {name} failed: {e}")
        return json.dumps({"error": str(e)})


def build_system_prompt(
    role: Optional[str],
    anomalies_text: str,
    freshness_text: str,
    state_context: dict,
) -> str:
    """
    Build the system prompt for the orchestrator.

    This prompt tells the LLM:
    - Who it is (voice analytics briefing agent)
    - Who the user is (CEO/Ops/Analyst)
    - What anomalies were detected
    - How fresh the data is
    - What conversation state we're in
    - How to respond (spoken, concise, role-appropriate)
    """
    role_guidance = {
        "ceo": (
            "The user is a CEO. They want:\n"
            "- Top 3 metrics only (orders, revenue, cancellation rate)\n"
            "- Strategic insights, not operational details\n"
            "- Risks and opportunities highlighted\n"
            "- Keep it under 30 seconds of speaking time (~75 words)\n"
            "- Confident, executive tone"
        ),
        "ops_manager": (
            "The user is an Operations Manager. They want:\n"
            "- City-level breakdowns of delays and issues\n"
            "- Flagged restaurants and delivery problems\n"
            "- Actionable operational insights\n"
            "- Keep it under 90 seconds (~225 words)\n"
            "- Direct, operational tone"
        ),
        "analyst": (
            "The user is a Data Analyst. They want:\n"
            "- Full data breakdown with numbers\n"
            "- Hourly trends, city comparisons, reason distributions\n"
            "- No time limit — be as detailed as needed\n"
            "- Data-heavy, precise tone"
        ),
    }

    current_state = state_context.get("current_state", "UNKNOWN")
    turn_count = state_context.get("turn_count", 0)

    return f"""You are a voice analytics briefing agent for a food delivery platform (similar to Swiggy).
You are speaking to the user via a phone call — your response will be converted to speech.

IMPORTANT RULES FOR VOICE RESPONSES:
- Speak naturally, as if talking on the phone. No bullet points, no markdown.
- Use numbers conversationally: "about forty-seven thousand orders" not "47,353"
- Round numbers for speech: "roughly 17 million in revenue" not "16,925,750.72"
- Lead with the most important insight first
- If anomalies were detected, mention them prominently at the start

USER ROLE:
{role_guidance.get(role, "Role unknown — provide a balanced overview.")}

ANOMALY SCAN RESULTS:
{anomalies_text}

DATA FRESHNESS:
{freshness_text}

CONVERSATION STATE: {current_state}
TURN NUMBER: {turn_count}
ALLOWED NEXT STATES: {state_context.get('allowed_transitions', [])}

CONVERSATION GUIDELINES BY STATE:
- BRIEFING: Deliver the main briefing. Lead with anomalies if any, then key metrics.
- DRILL_DOWN: User wants more detail. Go deeper on what they asked about.
- FOLLOW_UP: User has a related question. Answer it with supporting data.
- CLOSING: Summarize the key takeaway and say goodbye professionally.

Use the available tools to fetch real data before responding. Never make up numbers.
Always fetch data first, then build your response from the actual numbers."""


# ─── OpenAI ReAct loop ───

async def _run_openai(system_prompt: str, user_text: str) -> dict:
    """ReAct loop using OpenAI function calling (gpt-4o)."""
    import openai

    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]
    tool_calls_log = []
    total_tokens = 0

    max_iterations = 8
    for iteration in range(max_iterations):
        logger.info(f"[orchestrator/openai] ReAct iteration {iteration + 1}")

        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            tools=OPENAI_TOOLS,
            max_tokens=1024,
        )

        choice = response.choices[0]
        total_tokens += (response.usage.prompt_tokens + response.usage.completion_tokens)

        # If the model wants to call tools
        if choice.finish_reason == "tool_calls":
            # Add assistant message with tool calls to conversation
            messages.append(choice.message.model_dump())

            # Execute each tool call
            for tc in choice.message.tool_calls:
                tool_name = tc.function.name
                tool_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                logger.info(f"[orchestrator/openai] Tool call: {tool_name}({tool_args})")

                result = _execute_tool(tool_name, tool_args)
                tool_calls_log.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "iteration": iteration + 1,
                })

                # Add tool result to conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        else:
            # Final response — no more tool calls
            final_text = choice.message.content or ""
            return {
                "response": final_text,
                "tool_calls": tool_calls_log,
                "token_count": total_tokens,
            }

    # Safety: hit max iterations
    logger.warning(f"[orchestrator/openai] Hit max iterations ({max_iterations})")
    return {
        "response": "I apologize, I had trouble processing that request. Could you rephrase your question?",
        "tool_calls": tool_calls_log,
        "token_count": total_tokens,
    }


# ─── Anthropic ReAct loop ───

async def _run_anthropic(system_prompt: str, user_text: str) -> dict:
    """ReAct loop using Anthropic tool use (Claude)."""
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    messages = [{"role": "user", "content": user_text}]
    tool_calls_log = []
    total_tokens = 0

    max_iterations = 8
    for iteration in range(max_iterations):
        logger.info(f"[orchestrator/anthropic] ReAct iteration {iteration + 1}")

        response = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=1024,
            system=system_prompt,
            tools=ANTHROPIC_TOOLS,
            messages=messages,
        )

        total_tokens += response.usage.input_tokens + response.usage.output_tokens

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_args = block.input
                    logger.info(f"[orchestrator/anthropic] Tool call: {tool_name}({tool_args})")

                    result = _execute_tool(tool_name, tool_args)
                    tool_calls_log.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "iteration": iteration + 1,
                    })

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        else:
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text

            return {
                "response": final_text,
                "tool_calls": tool_calls_log,
                "token_count": total_tokens,
            }

    logger.warning(f"[orchestrator/anthropic] Hit max iterations ({max_iterations})")
    return {
        "response": "I apologize, I had trouble processing that request. Could you rephrase your question?",
        "tool_calls": tool_calls_log,
        "token_count": total_tokens,
    }


# ─── Public entry point ───

async def run_orchestrator(
    user_text: str,
    role: Optional[str],
    anomalies: list[dict],
    state_context: dict,
    prompt_version: Optional[str] = None,
) -> dict:
    """
    Run the ReAct loop.

    Args:
        user_text: what the user said
        role: detected role (ceo, ops_manager, analyst)
        anomalies: list of detected anomalies
        state_context: current conversation state
        prompt_version: which prompt version for A/B testing

    Returns:
        dict with:
        - response: the agent's spoken response
        - tool_calls: list of tools called (for logging)
        - token_count: total tokens used (for cost tracking)
        - latency_ms: how long it took
    """
    start_time = time.time()

    anomalies_text = format_anomalies_for_agent(anomalies)
    freshness_text = format_freshness_for_agent()

    system_prompt = build_system_prompt(role, anomalies_text, freshness_text, state_context)

    # Route to the right LLM provider
    provider = settings.LLM_PROVIDER.lower()
    logger.info(f"[orchestrator] Using provider: {provider}")

    if provider == "anthropic":
        result = await _run_anthropic(system_prompt, user_text)
    else:
        # Default to OpenAI
        result = await _run_openai(system_prompt, user_text)

    latency_ms = int((time.time() - start_time) * 1000)
    logger.info(
        f"[orchestrator] Response generated in {latency_ms}ms, "
        f"{len(result['tool_calls'])} tool calls, {result['token_count']} tokens"
    )

    result["latency_ms"] = latency_ms
    return result
