# Step 6 — ChromaDB RAG Setup

## What is RAG?

RAG = Retrieval-Augmented Generation. Instead of just asking Claude a question, we **search a knowledge base first** and give Claude the search results as extra context.

```
WITHOUT RAG:
User: "What's our AOV?"
Claude: "I don't know what AOV means in your company context"

WITH RAG:
User: "What's our AOV?"
  → Search ChromaDB for "AOV"
  → Found: "AOV = Average Order Value. Rs 350-400 benchmark..."
  → Pass definition + user question to Claude
Claude: "Your AOV yesterday was Rs 357, within the 350-400 benchmark..."
```

**Simple analogy**: RAG is like an open-book exam. Instead of relying on memory alone, the AI gets to check its notes before answering.

## Why two collections?

### Collection 1: Business Glossary (26 terms)
Definitions of business terms: AOV, GMV, CSAT, AHT, LD orders, etc.

**Why it matters**: The CEO says "GMV" and the Ops manager says "AHT" — the agent needs to know what these mean. Without the glossary, Claude might guess wrong or give a generic definition instead of one specific to food delivery.

### Collection 2: Query History (grows over time)
Past questions and the approach used to answer them.

**Why it matters**: This is the "learning" part. If someone asked "show me Mumbai cancellations" before, and someone asks "show me Delhi cancellations" later, we already know the approach — query the cancellations table filtered by city. Seeded with 6 examples, grows with every call.

## How it connects to the rest
- Orchestrator (Step 10) calls `search_glossary()` before generating a response
- Orchestrator calls `search_similar_queries()` to find relevant past approaches
- After each successful response, `store_query()` saves the new Q&A pair
- The more calls the system handles, the better retrieval gets

## Production reality (Swiggy connection)
Swiggy's Hermes V2: "Knowledge Base + RAG approach with vector-based few-shot retrieval." Their pipeline: metrics retrieval → table/column retrieval → few-shot SQL retrieval → structured prompt.
- Our glossary = their Knowledge Base (business term definitions)
- Our query history = their few-shot SQL retrieval (past examples improve accuracy)
- Result: Swiggy improved SQL generation accuracy from **54% to 93%** using this approach

---

## How Vector Search Works (the magic behind RAG)

When you add a document to ChromaDB:
1. The text is converted to a **vector** (a list of 384 numbers) using an embedding model
2. This vector captures the **meaning** of the text, not just the words

When you search:
1. Your query is also converted to a vector
2. ChromaDB finds documents whose vectors are **closest** to your query vector
3. "Closest" = most similar meaning

```
"What is AOV?" → vector [0.23, -0.41, 0.87, ...]
"Average Order Value" → vector [0.21, -0.39, 0.85, ...]  ← very close! (match)
"Delivery time" → vector [-0.15, 0.72, -0.33, ...]       ← very different (no match)
```

This is why searching "What is AOV?" finds the AOV definition even though the exact words "AOV" and "Average Order Value" are different — the **meaning** is similar.

---

## Key Files

### `glossary.py` — Business Term Definitions
- 26 terms across 8 categories: order metrics, financial, operational, cancellations, delivery, city, AI metrics, A/B testing
- Each term stored as: "TERM: full definition with context"
- `search_glossary(query, n_results=3)` — returns top 3 matching terms with relevance scores
- Uses ChromaDB's default embedding model (all-MiniLM-L6-v2, 80MB, runs locally)

### `query_history.py` — Learning From Past Queries
- Seeded with 6 example queries (2 CEO, 2 Ops, 2 Analyst)
- `store_query()` — saves a new Q&A after successful response
- `search_similar_queries(query, role)` — finds similar past queries, optionally filtered by role
- Grows over time — the system gets smarter with usage

---

## Glossary Categories

| Category | Terms | Example |
|----------|-------|---------|
| Order Metrics | AOV, GMV, Total Orders, Delivered Orders | "AOV = total revenue / total orders" |
| Financial | Net Revenue, Gross Revenue, Take Rate | "Take Rate = platform commission %" |
| Operational | AHT, CSAT, SLA, P95 Delivery Time | "CSAT = 1-5 rating, 4.0+ is good" |
| Cancellations | Cancellation Rate, Customer/Restaurant Cancellation | "Healthy range: 3-5%" |
| Delivery | LD Orders, DEP, First Mile, Last Mile | "LD = Long Distance, >7km radius" |
| City | Dark Store, Serviceable Area, Penetration Rate | "Dark Store = delivery-only warehouse" |
| AI Metrics | Confidence Score, Hallucination, Factfulness Score | "Below 0.5 confidence = fallback" |
| A/B Testing | Prompt Version, Traffic Split | "50/50 split between v1 and v2" |

---

## Test Results

```
Search: "What is our AOV?"
  [0.19] AOV: Average Order Value. Calculated as total revenue divided by...

Search: "cancellation rate is too high"
  [0.30] Customer Cancellation: Order cancelled by the customer...
  [-0.03] Restaurant Cancellation: Order cancelled by the restaurant...
  [-0.04] Cancellation Rate: Percentage of orders cancelled...

Search: "Give me the top numbers" (role=ceo)
  [-0.21] Question: What are today's overall numbers? → Fetch aggregated orders, revenue...

Search: "Which cities have delays?" (role=ops_manager)
  [0.41] Question: Show me the city-wise breakdown of delays → Fetch delivery time per city...
```

Scores: higher = more relevant. The correct terms/queries rank first every time.

---

## What breaks if we remove it

| If you remove... | What breaks |
|-----------------|-------------|
| Glossary collection | Agent doesn't know business jargon. "What's CSAT?" gets a generic answer. |
| Query history | No learning from past interactions. Every query starts from scratch. |
| `seed_glossary()` | Empty glossary. Agent has no business context on first run. |
| `seed_query_history()` | No few-shot examples. Orchestrator doesn't know good approaches for common questions. |

## Where we simplified vs production

| Us | Production (Swiggy) |
|---|---|
| ChromaDB in-process (single file) | Dedicated vector DB cluster (Pinecone, Weaviate) |
| 26 terms, 6 seed queries | Thousands of terms, millions of historical queries |
| Default embedding model (MiniLM, 80MB) | Fine-tuned embedding model for domain-specific accuracy |
| No embedding updates | Periodic re-embedding as business terms evolve |
| Single collection per type | Sharded collections per business unit (charter) |

---

## Interview questions

### "What is RAG and why did you use it?"
**Answer**: "RAG is Retrieval-Augmented Generation — before asking the LLM to generate a response, I search a knowledge base for relevant context and include it in the prompt. I used it for two things: a business glossary (so the agent knows what AOV, CSAT, AHT mean in our specific context) and query history (past questions and approaches, similar to few-shot learning). Swiggy's Hermes system uses the same pattern — their Knowledge Base + vector-based few-shot retrieval improved SQL accuracy from 54% to 93%."

### "How does vector search work?"
**Answer**: "Each document is converted to a vector — a list of numbers that represents its meaning. When I search, the query is also vectorized, and ChromaDB finds the documents whose vectors are closest. This means 'What is AOV?' matches 'Average Order Value' even though they share zero words — because the meaning is similar. It's like how you'd understand that 'automobile' and 'car' mean the same thing."

### "Why two separate collections?"
**Answer**: "Different purposes require different retrieval strategies. The glossary is static — term definitions that rarely change. Query history is dynamic — it grows with every call. Separating them means I can search only what's relevant: when the user mentions jargon, search glossary; when building a response approach, search history. Swiggy did the same with charter-based compartmentalization — separate knowledge bases per business unit."
