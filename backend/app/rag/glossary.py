"""
Business glossary RAG collection.

Stores definitions of business terms so the voice agent
never says "I don't know what that means."

When the orchestrator gets a user query, it searches this collection
for relevant terms and includes the definitions in the Claude prompt.

This is the equivalent of Swiggy's Knowledge Base in their Hermes system.
"""

import chromadb
from pathlib import Path

# Persistent storage — survives server restarts
CHROMA_PATH = Path(__file__).parent.parent.parent / "data" / "chroma"

_client = None
_collection = None


def _get_collection():
    """Lazy-initialize ChromaDB client and glossary collection."""
    global _client, _collection
    if _collection is None:
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        _collection = _client.get_or_create_collection(
            name="business_glossary",
            metadata={"description": "Business term definitions for voice briefings"},
        )
    return _collection


# --- Business glossary terms ---
# Each entry: (term, definition, category)
# These are terms that enterprise users (CEO, Ops, Analyst) use daily

GLOSSARY_TERMS = [
    # Order metrics
    ("AOV", "Average Order Value. Calculated as total revenue divided by total orders. Higher AOV means customers are spending more per order. Swiggy benchmark: Rs 350-400 for food delivery.", "order_metrics"),
    ("GMV", "Gross Merchandise Value. Total value of all orders before discounts, commissions, and refunds. This is the top-line number CEOs track. Different from net revenue.", "order_metrics"),
    ("Total Orders", "Count of all orders placed in a given period. Includes delivered, cancelled, and in-progress. The most basic volume metric.", "order_metrics"),
    ("Delivered Orders", "Orders that successfully reached the customer. Total Orders minus cancellations and failures. This is what matters for revenue.", "order_metrics"),

    # Financial metrics
    ("Net Revenue", "Revenue after subtracting discounts, refunds, delivery partner payouts, and restaurant commissions. Typically 25-30% of GMV for food delivery platforms.", "financial"),
    ("Gross Revenue", "Total revenue before deductions. Includes the full order value. Always higher than net revenue.", "financial"),
    ("Take Rate", "Platform's commission percentage from each order. Typically 15-25% for food delivery. Higher take rate means more revenue per order but can strain restaurant relationships.", "financial"),

    # Operational metrics
    ("AHT", "Average Handling Time. Time from when a support interaction starts to when it's resolved. Lower is better. Swiggy targets under 5 minutes for voice support.", "operational"),
    ("CSAT", "Customer Satisfaction Score. Usually 1-5 rating collected after interaction. Industry benchmark: 4.0+ is good, 4.5+ is excellent.", "operational"),
    ("SLA", "Service Level Agreement. Promised response/delivery time. For delivery: typically 30-45 minutes. For support: first response within 60 seconds.", "operational"),
    ("P95 Delivery Time", "95th percentile delivery time. Means 95% of orders are delivered faster than this value. More meaningful than average because it captures the worst-case experience.", "operational"),

    # Cancellation metrics
    ("Cancellation Rate", "Percentage of orders cancelled out of total orders. Calculated as (cancelled orders / total orders) * 100. Healthy range: 3-5%. Above 5% needs investigation.", "cancellations"),
    ("Customer Cancellation", "Order cancelled by the customer. Common reasons: changed mind, found better option, delivery too slow. Usually 60-70% of all cancellations.", "cancellations"),
    ("Restaurant Cancellation", "Order cancelled by the restaurant. Reasons: out of stock, closing early, too many orders. Usually 20-30% of all cancellations.", "cancellations"),

    # Delivery metrics
    ("LD Orders", "Long Distance orders. Deliveries beyond the standard radius (typically >7km). These have higher delivery times and costs. Important for ops managers to monitor.", "delivery"),
    ("DEP", "Delivery Efficiency Percentage. Ratio of actual delivery time to estimated delivery time. Below 100% means faster than promised (good). Above 100% means delays.", "delivery"),
    ("First Mile", "Time from order placement to restaurant accepting and starting preparation. Delays here indicate restaurant-side issues.", "delivery"),
    ("Last Mile", "Time from food pickup to customer delivery. Delays here indicate delivery partner or route issues.", "delivery"),

    # City/region metrics
    ("Dark Store", "A delivery-only warehouse (no walk-in customers) used for Instamart quick commerce. Positioned in high-demand areas for 10-minute delivery.", "city"),
    ("Serviceable Area", "Geographic region where delivery is available. Defined by radius from restaurants or dark stores. Expanding this means more customers but longer delivery times.", "city"),
    ("Penetration Rate", "Percentage of potential customers in an area who have placed at least one order. Low penetration = growth opportunity. High penetration = focus on retention.", "city"),

    # Agent/AI metrics
    ("Confidence Score", "How certain the AI agent is about its response. Scale 0-1. Below 0.5 triggers fallback to human. Used for quality control.", "ai_metrics"),
    ("Hallucination", "When the AI generates information that isn't supported by the actual data. Example: claiming orders are up when they're actually down. Critical failure mode.", "ai_metrics"),
    ("Factfulness Score", "Measures whether the AI response contains only verifiable facts from the data. Score 1-3. Below 2 means the response may contain inaccuracies.", "ai_metrics"),

    # A/B testing terms
    ("Prompt Version", "Different versions of the AI prompt being tested. v1 might be concise, v2 might be detailed. The winner is the one with higher evaluation scores.", "ab_testing"),
    ("Traffic Split", "How calls are divided between prompt versions. 50/50 means equal split. Can be adjusted based on early results.", "ab_testing"),
]


def seed_glossary():
    """Populate the glossary collection with business terms."""
    collection = _get_collection()

    # Check if already seeded
    if collection.count() > 0:
        return

    ids = []
    documents = []
    metadatas = []

    for i, (term, definition, category) in enumerate(GLOSSARY_TERMS):
        ids.append(f"term_{i}")
        # The document is what gets embedded and searched
        documents.append(f"{term}: {definition}")
        metadatas.append({"term": term, "category": category})

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    print(f"[rag] Seeded glossary with {len(ids)} terms")


def search_glossary(query: str, n_results: int = 3) -> list[dict]:
    """
    Search the glossary for terms relevant to the user's query.

    Uses vector similarity — the query is embedded and compared
    against all term embeddings. Returns the closest matches.

    Args:
        query: what the user asked (e.g., "What's our AOV trend?")
        n_results: how many terms to return

    Returns:
        List of dicts with term, definition, category, relevance_score
    """
    collection = _get_collection()

    if collection.count() == 0:
        seed_glossary()

    results = collection.query(query_texts=[query], n_results=n_results)

    matches = []
    for i in range(len(results["ids"][0])):
        doc = results["documents"][0][i]
        meta = results["metadatas"][0][i]
        distance = results["distances"][0][i]

        # Split "TERM: definition" back apart
        term = meta["term"]
        definition = doc.split(": ", 1)[1] if ": " in doc else doc

        matches.append({
            "term": term,
            "definition": definition,
            "category": meta["category"],
            "relevance_score": round(1 - distance, 3),  # convert distance to similarity
        })

    return matches


if __name__ == "__main__":
    seed_glossary()
    # Test search
    results = search_glossary("What's our average order value?")
    for r in results:
        print(f"  {r['term']} ({r['relevance_score']}) — {r['definition'][:60]}...")
