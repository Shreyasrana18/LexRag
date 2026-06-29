import httpx
import json
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.constants import LLM_SYSTEM_PROMPT, NO_EXCERPTS_INSTRUCTION, ANSWER_INSTRUCTIONS, SHORT_SUMMARY_INSTRUCTIONS

class Settings(BaseSettings):
    LLM_URL: str
    LLM_MODEL: str
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings() # type: ignore

def buildPrompt(chunks: list[dict], query: str, chat_history: list[dict] | None = None) -> str:
    prompt = LLM_SYSTEM_PROMPT + "\n\n"

    if chunks:
        prompt += "RELEVANT CASE EXCERPTS:\n"
        for i, chunk in enumerate(chunks, 1):
            page_label = chunk.get("page_range") or f"Chunk {chunk.get('chunk_index', i)}"
            prompt += f"[Excerpt {i} | {page_label}]\n{chunk['text']}\n\n"
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

async def llmsummarize(existing_summary: str, new_chunk: str) -> str:
    prompt = f"Existing summary:\n{existing_summary}\n\nNew text to incorporate:\n{new_chunk}\n\nPlease provide an updated summary that incorporates the new text. If the new text does not add any new information, you can return the existing summary."
    async for chunk in safe_stream(llmsearch(prompt, stream=False)):
        existing_summary = chunk
    return existing_summary

async def generateShortSummary(summary: str) -> str:
    prompt = SHORT_SUMMARY_INSTRUCTIONS.format(summary=summary)

    response = ""
    async for chunk in llmsearch(prompt, stream=False):
        response += chunk
    return response.strip()


async def generateCaseSelectionMessage(query: str, cases: list[dict]) -> str:
    prompt = f"""User searched for: "{query}"

These cases were found as relevant. Write a single short paragraph (2-3 sentences max) explaining what these cases have in common and why they match the query. Be direct, no fluff.

Cases:
{chr(10).join([f"- {c['title']}: {c['short_summary']}" for c in cases])}

Response:"""

    response = ""
    async for chunk in llmsearch(prompt, stream=False):
        response += chunk
    return response.strip()

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