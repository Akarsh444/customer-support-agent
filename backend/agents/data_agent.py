"""
Data Agent
----------
An agent that answers billing/account questions by calling tools
from the SQL MCP server. The LLM (Gemini) decides which tools to
call based on the user's question — that decision-making is what
makes it 'agentic'.

Flow:
  user question -> LLM plans -> calls MCP tool(s) -> reads results
  -> forms grounded answer
"""
import os
import asyncio
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

# Load .env from project root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Path to the MCP server script (the agent launches it as a subprocess)
SQL_SERVER_PATH = os.path.join(os.path.dirname(__file__), "..", "mcp_servers", "sql_server.py")

# System prompt — defines the agent's behaviour and grounding rules
SYSTEM_PROMPT = """You are a Data Agent for a customer support team.
You answer questions about customer billing, invoices, and accounts.

Rules:
- Use the available tools to look up real data. Never guess or make up numbers.
- Base every factual claim strictly on tool results.
- When you find an overbilling, state the billed amount, the expected amount,
  the difference, and the reason.
- If the data doesn't contain the answer, say so clearly.
- Be concise and factual.
"""


async def run_data_agent(question: str) -> str:
    """Run the Data Agent on a single question and return its answer."""

    # 1. Set up the LLM (Gemini via LangChain — swappable to any other model)
    llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=GOOGLE_API_KEY,
    temperature=0,
    max_output_tokens=1000,
    )

    # 2. Connect to our SQL MCP server. The adapter discovers its tools
    #    and converts them into LangChain-compatible tools automatically.
    client = MultiServerMCPClient(
        {
            "databricks-sql": {
                "url": "http://127.0.0.1:8000/mcp",
                "transport": "streamable_http",
            }
        }
    )
    print("Connecting to MCP...")
    tools = await client.get_tools()

    # 3. Build the agent — LLM + tools + system prompt
    agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)

    result = await agent.ainvoke(
    {"messages": [{"role": "user", "content": question}]}
    )

    final_message = result["messages"][-1]
    content = final_message.content

    # Gemini returns content as a list of blocks; extract just the text
    if isinstance(content, list):
        text_parts = [block.get("text", "") for block in content if isinstance(block, dict)]
        return "\n".join(text_parts).strip()
    return content


# Quick standalone test
if __name__ == "__main__":
    async def main():
        question = "Why was Acme Corp overbilled in May 2025?"
        print(f"Question: {question}\n")
        answer = await run_data_agent(question)
        print(f"Answer:\n{answer}")

    asyncio.run(main())