"""
Portfolio chatbot backend — light on purpose.
One route, one job: answer questions about Kashish using knowledge_base.md,
and refuse anything that isn't in there. Powered by Groq's free API.
"""

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

KB_PATH = Path(__file__).parent / "knowledge_base.md"
KNOWLEDGE_BASE = KB_PATH.read_text(encoding="utf-8")

SYSTEM_PROMPT = f"""You are Kashish's portfolio assistant — a small chatbot embedded in her
personal site so visitors (recruiters, engineers, curious people) can ask about her.

Answer ONLY using the KNOWLEDGE BASE below. This is a hard rule, not a suggestion:
- If the answer is in the knowledge base, answer naturally and conversationally, in 1-4 sentences.
- If the question is about Kashish but the knowledge base doesn't cover it, say you don't have
  that detail yet and suggest what you *can* answer (skills, experience, projects, education).
- If the question is unrelated to Kashish entirely (general coding help, trivia, world news,
  writing essays, anything off-topic), politely decline and steer back to her portfolio. Do not
  answer the off-topic question even partially.
- Never invent facts, projects, dates, or links that aren't in the knowledge base below.
- Keep replies short and friendly — this is a portfolio widget, not an essay generator.

KNOWLEDGE BASE:
---
{KNOWLEDGE_BASE}
---
"""

app = FastAPI(title="Kashish Portfolio Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your deployed frontend domain before going live
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []  # [{role: "user"|"assistant", content: "..."}]


class ChatResponse(BaseModel):
    reply: str


@app.get("/api/health")
def health():
    return {"status": "ok", "model": GROQ_MODEL}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not GROQ_API_KEY:
        raise HTTPException(500, "GROQ_API_KEY is not set on the server.")

    if not req.message.strip():
        raise HTTPException(400, "Message can't be empty.")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    # keep only the last few turns — this bot is meant to be light, not a full memory system
    messages += req.history[-6:]
    messages.append({"role": "user", "content": req.message})

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 300,
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(GROQ_URL, json=payload, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(502, f"Groq API error: {e.response.text}")
        except httpx.RequestError as e:
            raise HTTPException(502, f"Could not reach Groq API: {e}")

    data = resp.json()
    reply = data["choices"][0]["message"]["content"]
    return ChatResponse(reply=reply)