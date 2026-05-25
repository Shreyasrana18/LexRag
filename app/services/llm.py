import httpx
import json
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.constants import LLM_SYSTEM_PROMPT, NO_EXCERPTS_INSTRUCTION, ANSWER_INSTRUCTIONS

class Settings(BaseSettings):
    LLM_URL: str
    LLM_MODEL: str
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings() # type: ignore

def buildPrompt(records: list[str], query: str, chat_history: list[dict] | None = None) -> str:
    prompt = LLM_SYSTEM_PROMPT + "\n\n"

    if records:
        prompt += "RELEVANT CASE EXCERPTS:\n"
        for i, record in enumerate(records, 1):
            prompt += f"[Excerpt {i}]\n{record}\n\n"
    else:
        prompt += f"NOTE: {NO_EXCERPTS_INSTRUCTION}\n\n"

    if chat_history:
        prompt += "CONVERSATION HISTORY:\n"
        for msg in chat_history:
            role = "User" if msg["role"] == "user" else "Assistant"
            prompt += f"{role}: {msg['content']}\n"
        prompt += "\n"

    prompt += f"CURRENT QUESTION: {query}\n\nINSTRUCTIONS:\n{ANSWER_INSTRUCTIONS}\n\nANSWER:"
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