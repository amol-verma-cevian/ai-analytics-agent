"""
Query history RAG collection.

Stores past user questions and the approach used to answer them.
When a similar question comes in, we retrieve the past approach
and give it to Claude as a "few-shot example."

This is the equivalent of Swiggy's "few-shot SQL retrieval" in Hermes V2 —
they used historical queries as examples to improve generation accuracy
from 54% to 93%.

For us, it means:
- "Show Mumbai orders" was answered by querying orders table filtered by city
- Next time someone asks "Show Delhi orders", we already know the approach
"""

import chromadb
from datetime import datetime
from pathlib import Path

CHROMA_PATH = Path(__file__).parent.parent.parent / "data" / "chroma"

_client = None
_collection = None


def _get_collection():
    """Lazy-initialize the query history collection."""
    global _client, _collection
    if _collection is None:
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        _collection = _client.get_or_create_collection(
            name="query_history",
            metadata={"description": "Past user queries and how they were answered"},
        )
    return _collection


def store_query(
    user_query: str,
    role: str,
    metrics_used: list[str],
    approach: str,
    call_id: str,
):
    """
    Store a successfully answered query for future retrieval.

    Args:
        user_query: what the user asked
        role: ceo / ops_manager / analyst
        metrics_used: which data tables/metrics were queried
        approach: how the answer was constructed
        call_id: which call this came from
    """
    collection = _get_collection()
    doc_id = f"query_{call_id}_{datetime.now().timestamp()}"

    collection.add(
        ids=[doc_id],
        documents=[f"Question: {user_query}\nApproach: {approach}"],
        metadatas=[{
            "role": role,
            "metrics_used": ",".join(metrics_used),
            "call_id": call_id,
            "timestamp": datetime.now().isoformat(),
        }],
    )


def search_similar_queries(query: str, role: str = None, n_results: int = 3) -> list[dict]:
    """
    Find past queries similar to the current one.

    Args:
        query: current user question
        role: optionally filter by role (CEO queries are different from Ops)
        n_results: how many past queries to return

    Returns:
        List of dicts with past question, approach, and similarity score
    """
    collection = _get_collection()

    if collection.count() == 0:
        return []

    where_filter = {"role": role} if role else None

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where_filter,
    )

    matches = []
    for i in range(len(results["ids"][0])):
        doc = results["documents"][0][i]
        meta = results["metadatas"][0][i]
        distance = results["distances"][0][i]

        matches.append({
            "past_query": doc,
            "role": meta["role"],
            "metrics_used": meta["metrics_used"].split(","),
            "similarity_score": round(1 - distance, 3),
        })

    return matches


def seed_query_history():
    """Seed with example queries to bootstrap the system."""
    collection = _get_collection()

    if collection.count() > 0:
        return

    example_queries = [
        {
            "query": "What are today's overall numbers?",
            "role": "ceo",
            "metrics": ["orders", "revenue", "cancellations"],
            "approach": "Fetch yesterday's aggregated orders, revenue, and cancellation rate across all cities. Present top-line numbers with week-on-week comparison.",
        },
        {
            "query": "Are there any issues I should know about?",
            "role": "ceo",
            "metrics": ["anomalies", "cancellations"],
            "approach": "Run anomaly detection scan. Report any metric deviations above threshold. Prioritize by severity: critical > high > medium.",
        },
        {
            "query": "Show me the city-wise breakdown of delays",
            "role": "ops_manager",
            "metrics": ["orders", "hourly_trends", "cities"],
            "approach": "Fetch delivery time data per city. Compare against SLA targets. Identify cities with P95 delivery time above threshold. Show hourly trend for worst-performing city.",
        },
        {
            "query": "Which restaurants have the most complaints?",
            "role": "ops_manager",
            "metrics": ["restaurants"],
            "approach": "Query restaurants sorted by complaints_last_7d descending. Filter for complaints above threshold (8). Include avg_rating and avg_prep_time for context.",
        },
        {
            "query": "Give me the full cancellation breakdown with reasons",
            "role": "analyst",
            "metrics": ["cancellations", "cities", "hourly_trends"],
            "approach": "Fetch cancellations by city and by reason. Calculate percentage distribution of reasons. Show hourly pattern to identify peak cancellation times. Include week-on-week trend.",
        },
        {
            "query": "How is Mumbai performing compared to last week?",
            "role": "analyst",
            "metrics": ["orders", "revenue", "cancellations"],
            "approach": "Fetch this week vs last week data for Mumbai specifically. Calculate percentage change for orders, revenue, and cancellation rate. Identify which metrics improved and which declined.",
        },
    ]

    for i, ex in enumerate(example_queries):
        collection.add(
            ids=[f"seed_{i}"],
            documents=[f"Question: {ex['query']}\nApproach: {ex['approach']}"],
            metadatas=[{
                "role": ex["role"],
                "metrics_used": ",".join(ex["metrics"]),
                "call_id": "seed",
                "timestamp": "seed",
            }],
        )

    print(f"[rag] Seeded query history with {len(example_queries)} examples")


if __name__ == "__main__":
    seed_query_history()
