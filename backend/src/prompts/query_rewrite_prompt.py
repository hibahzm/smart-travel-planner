"""
Prompt used by gpt-4o-mini to rewrite a user query into an optimised RAG search query.

Why a separate rewrite step?
Conversational queries like "I want somewhere warm, not too touristy, cheap, with hiking"
are poor vector search queries because the embeddings spread across vague adjectives.
Rewriting to "warm budget hiking destination low crowds" concentrates signal into the
dimensions the embedding model weights most.

This is a one-shot call (not part of the agent loop) — cheap and fast with gpt-4o-mini.
"""

QUERY_REWRITE_PROMPT = """\
You are a search query optimiser for a travel knowledge base.

Convert the user's natural-language travel question into a short, dense search query \
(5–15 words) that will maximise cosine similarity with travel article embeddings.

Rules:
- Keep only concrete travel concepts: destination types, activities, climate, budget level.
- Remove filler words ("I want", "please", "maybe", "I think").
- Include any explicitly named destination.
- Do NOT add information not present in the original query.
- Return ONLY the rewritten query. No explanation, no punctuation at the end.

User query: {user_query}
Rewritten query:"""
