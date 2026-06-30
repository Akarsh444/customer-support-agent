"""
FastAPI backend
---------------
Exposes the Data Agent over HTTP so the React UI can call it.
The UI sends a question to /ask, this calls run_data_agent(),
and returns the answer as JSON.
"""
import sys
import os

# Allow importing from the backend package (one level up from api/)
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agents.supervisor import run_supervisor

app = FastAPI(title="Customer Support Data Agent API")

# Allow the React dev server (localhost:5173) to call this API.
# Without CORS, the browser blocks requests from a different port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# The shape of the incoming request body: { "question": "..." }
class AskRequest(BaseModel):
    question: str


# The shape of the response: { "answer": "..." }
class AskResponse(BaseModel):
    answer: str


@app.get("/")
async def health():
    """Simple health check — confirms the API is running."""
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    """
    Receive a question from the UI, run the Data Agent on it,
    and return the grounded answer.
    """
    answer = await run_supervisor(request.question)
    return AskResponse(answer=answer)