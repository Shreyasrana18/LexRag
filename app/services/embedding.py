import asyncio
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from sentence_transformers import SentenceTransformer

class Settings(BaseSettings):
    HF_TOKEN: str
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings() # type: ignore
model = SentenceTransformer('BAAI/bge-base-en-v1.5', token=settings.HF_TOKEN)
_executor = ThreadPoolExecutor(max_workers=2)

class TextRequest(BaseModel):
    texts: list[str]

def generateEmbeddings(text: str) -> list[float]:
    return model.encode(text, normalize_embeddings=True).tolist()

async def generateEmbeddingsAsync(text: str) -> list[float]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        partial(generateEmbeddings, text)
    )