"""
Manual retrieval tests — run before plugging RAG into the agent.

These verify that the embedding + pgvector search returns sensible results
for real queries. We test:
  1. Specific destination query → correct destination returned
  2. Activity query → relevant activity content returned
  3. Budget query → budget destinations returned
  4. Cross-destination comparison → top result is the better match

Run:
  uv run python rag/test_retrieval.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from openai import AsyncOpenAI

import src.core.lifespan as ls
from src.core.config import settings
from src.db.engine import create_engine, dispose_engine
from src.db.session import get_session_factory

TEST_QUERIES = [
    {
        "id": 1,
        "query": "warm beach destination for relaxation not too crowded",
        "destination": None,
        "expected_contains": ["beach", "Bali", "Maldives", "Relaxation", "Seychelles"],
        "note": "Should return beach/relaxation content",
    },
    {
        "id": 2,
        "query": "Machu Picchu hiking altitude tips booking",
        "destination": "Peru",
        "expected_contains": ["Machu Picchu", "altitude", "book", "permit"],
        "note": "Destination-filtered query should find Inca Trail content",
    },
    {
        "id": 3,
        "query": "budget travel Southeast Asia street food cheap accommodation",
        "destination": None,
        "expected_contains": ["VND", "budget", "Thailand", "Vietnam", "street food"],
        "note": "Budget query should surface Vietnam/Thailand cost sections",
    },
    {
        "id": 4,
        "query": "northern lights winter Iceland aurora forecast",
        "destination": "Iceland",
        "expected_contains": ["aurora", "northern lights", "forecast", "dark"],
        "note": "Iceland-filtered query should return aurora content",
    },
    {
        "id": 5,
        "query": "wine region vineyard tour tasting accommodation",
        "destination": None,
        "expected_contains": ["wine", "winery", "vineyard", "tasting"],
        "note": "Should surface Georgia Kakheti or Portugal Douro wine content",
    },
]


async def run_test(query: str, destination: str | None, k: int, db) -> list[dict]:
    from src.services.embeddings import embed_text
    from sqlalchemy import text as sqltext

    embedding = await embed_text(query)
    emb_str = "[" + ",".join(str(x) for x in embedding) + "]"

    if destination:
        stmt = sqltext("""
            SELECT destination, source, content,
                   1 - (embedding <=> CAST(:emb AS vector)) AS similarity
            FROM document_chunks
            WHERE destination ILIKE :dest
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :k
        """).bindparams(emb=emb_str, dest=f"%{destination}%", k=k)
    else:
        stmt = sqltext("""
            SELECT destination, source, content,
                   1 - (embedding <=> CAST(:emb AS vector)) AS similarity
            FROM document_chunks
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :k
        """).bindparams(emb=emb_str, k=k)

    result = await db.execute(stmt)
    return [
        {
            "destination": r.destination,
            "similarity": round(float(r.similarity), 4),
            "preview": r.content[:200],
        }
        for r in result.fetchall()
    ]


async def main():
    ls._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    await create_engine()
    session_factory = get_session_factory()

    print("=" * 70)
    print("RAG RETRIEVAL TESTS")
    print("=" * 70)

    passed = 0
    failed = 0

    async with session_factory() as db:
        for test in TEST_QUERIES:
            print(f"\nTest {test['id']}: {test['note']}")
            print(f"  Query: '{test['query']}'")
            if test["destination"]:
                print(f"  Filter: destination='{test['destination']}'")

            results = await run_test(test["query"], test["destination"], k=4, db=db)

            print(f"  Results ({len(results)} chunks):")
            for i, r in enumerate(results):
                print(f"    [{i+1}] {r['destination']} (sim={r['similarity']:.4f})")
                print(f"         {r['preview'][:120]}...")

            # Check if any expected keyword appears in results
            combined = " ".join(r["preview"] for r in results).lower()
            hits = [kw for kw in test["expected_contains"] if kw.lower() in combined]
            if hits:
                print(f"  ✓ PASS — found expected terms: {hits}")
                passed += 1
            else:
                print(f"  ✗ FAIL — none of {test['expected_contains']} found in results")
                failed += 1

    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed out of {len(TEST_QUERIES)} tests")
    print("=" * 70)

    await ls._openai_client.close()
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
