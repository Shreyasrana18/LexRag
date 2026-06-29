from sentence_transformers import CrossEncoder
from concurrent.futures import ThreadPoolExecutor

model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
_executor = ThreadPoolExecutor(max_workers=2)

def _rerank(query: str, chunks: list[dict]) -> list[dict]:
    pairs = [(query, chunk["text"]) for chunk in chunks]
    scores = model.predict(pairs)
    for chunk, score in zip(chunks, scores):
        chunk["score"] = float(score)
    return sorted(chunks, key=lambda x: x["score"], reverse=True)

async def rerank(query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    import asyncio
    from functools import partial
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        partial(_rerank, query, chunks)
    )