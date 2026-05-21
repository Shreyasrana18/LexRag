import httpx
import json
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    LLM_URL: str
    LLM_MODEL: str
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings() # type: ignore

def buildPrompt(records: list[str], query: str) -> str:
    prompt = "You are a legal research assistant. Based on the following case chunks, answer the question:\n\n"
    for record in records:
        prompt += f"Case Text: {record}\n\n"
    prompt += f"Question: {query}\nAnswer:"
    return prompt

async def safe_stream(generator):
    try:
        async for chunk in generator:
            yield chunk
    except RuntimeError as e:
        yield "The AI service is currently unavailable. Please try again later."
    except Exception as e:
        yield "An unexpected error occurred. Please try again later."

async def llmsearch(query: str, stream: bool = False):
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            settings.LLM_URL + "/api/generate",
            json={
                "model": settings.LLM_MODEL,
                "stream": stream,
                "prompt": query
            }
        ) as response:
            if response.status_code != 200:
                raise RuntimeError(f"LLM search failed with status {response.status_code}")
            
            async for line in response.aiter_lines():
                if line:
                    chunk = json.loads(line)
                    yield chunk["response"]
                    if chunk.get("done"):
                        break