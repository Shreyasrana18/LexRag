from arq import ArqRedis

arq_pool: ArqRedis | None = None

def get_arq_pool() -> ArqRedis:
    if arq_pool is None:
        raise RuntimeError("ARQ pool not initialized")
    return arq_pool

async def health_check() -> str:
    try:
        if arq_pool is None:
            return "error"
        await arq_pool.ping()
        return "ok"
    except Exception:
        return "error"