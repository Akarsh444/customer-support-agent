"""
Supervisor Agent
----------------
The orchestrator. Receives a user question, decides which specialist
agent(s) are needed, calls them, and combines their results into one
grounded answer.

The specialist agents are wrapped as TOOLS:
  - ask_data_agent   -> runs the Data Agent (reads billing/customer data)
  - ask_action_agent -> runs the Action Agent (performs real operations)
  (ask_search_agent is added later, when the Search Agent exists — one
   more tool, no rewrite.)

Same model-agnostic LangChain pattern as the specialists. The Supervisor
itself is a ReAct agent whose "tools" call the existing agent functions.
"""
import os
import asyncio
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

# Import the existing specialist agent entry points. We reuse them as-is.
from agents.data_agent import run_data_agent
from agents.action_agent import run_action_agent

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")


# --- SPECIALIST AGENTS WRAPPED AS TOOLS ---
# Each tool is a thin wrapper that calls an existing specialist agent and
# returns its answer. The Supervisor's LLM decides when to call each one,
# based on the docstrings below (which act as the tool descriptions).

@tool
async def ask_data_agent(question: str) -> str:
    """
    Ask the Data Agent a question about customer billing, invoices, or
    accounts. Use this to RETRIEVE or LOOK UP information — for example
    "why was Acme overbilled in May", "which customers are overbilled",
    "what is Acme's plan". Returns a grounded answer from the data.
    """
    return await run_data_agent(question)


@tool
async def ask_action_agent(request: str) -> str:
    """
    Ask the Action Agent to PERFORM an operation that changes data. Use
    this to DO something — for example "apply a correction to invoice
    INV011", "create a support case for Acme", "set account C009 to
    Active". Returns confirmation of the action performed.
    """
    return await run_action_agent(request)


# The system prompt defines how the Supervisor routes and combines.
SYSTEM_PROMPT = """You are the Supervisor of a customer support team.
You coordinate two specialist agents to answer the user's request:

- ask_data_agent: for RETRIEVING information (billing, invoices, accounts).
- ask_action_agent: for PERFORMING operations that change data (apply a
  correction, create a case, update account status).

How to work:
- Read the user's request and decide which specialist(s) are needed.
- If the request only needs information, call ask_data_agent.
- If the request only needs an action, call ask_action_agent.
- If it needs both (e.g. "why was Acme overbilled, and open a case"),
  call ask_data_agent first to get the facts, then ask_action_agent to
  perform the action, using the facts you learned.
- Combine the specialists' results into one clear, grounded final answer.
- Do not invent data. Only state what the specialists returned.
"""


# Runs the full supervisor loop for one request: plan -> call specialist
# tool(s) -> combine -> final answer. Returns the final answer text.
async def run_supervisor(question: str) -> str:
    """Run the Supervisor on a single user question and return its answer."""

    # 1. The Supervisor's own LLM (Gemini via LangChain — swappable).
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=GOOGLE_API_KEY,
        temperature=0,
        max_output_tokens=1500,
    )

    # 2. The specialist agents are the Supervisor's tools.
    tools = [ask_data_agent, ask_action_agent]

    # 3. Build the ReAct agent: it reasons about the request, calls the
    #    right specialist tool(s), reads their answers, and synthesises.
    agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": question}]}
    )

    # Extract the clean final-answer text (Gemini returns content as blocks).
    final_message = result["messages"][-1]
    content = final_message.content
    if isinstance(content, list):
        text_parts = [block.get("text", "") for block in content if isinstance(block, dict)]
        return "\n".join(text_parts).strip()
    return content


# Quick standalone test — exercises routing across all three cases.
if __name__ == "__main__":
    async def main():
        # A combined question: needs the Data Agent (facts) AND the Action
        # Agent (open a case). This proves orchestration of both.
        question = "Why was Umbrella Co overbilled, and apply a correction to invoice INV016 setting it to 6000."
        print(f"Question: {question}\n")
        answer = await run_supervisor(question)
        print(f"Answer:\n{answer}")

    asyncio.run(main())