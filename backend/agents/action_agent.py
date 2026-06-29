"""
Action Agent
------------
Performs deterministic support operations — customer lookup and case
creation — by calling tools from the Action MCP server (Unity Catalog
Functions). The LLM (Gemini) decides which tool to call based on the
request. Same model-agnostic LangChain pattern as the Data Agent.

Flow:
  request -> LLM plans -> calls UC Function tool(s) via MCP -> result
"""
import os
import asyncio
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# The system prompt defines the agent's behaviour. Unlike the Data Agent
# (which only reads), this agent performs operations — so it is told to
# use the action tools and report exactly what was done.
SYSTEM_PROMPT = """You are an Action Agent for a customer support team.
You perform support operations: looking up customer accounts and creating
support cases.

Rules:
- Use the available tools to perform the requested operation. Do not invent data.
- For a customer lookup, return the account details from the tool result.
- For case creation, confirm exactly what the tool reports was created.
- If a request cannot be completed with the available tools, say so clearly.
- Be concise and factual.
"""

# Runs the full agent loop for one request:
#   request -> LLM picks a tool -> tool runs via MCP (UC Function)
#   -> LLM reports the result. Returns the final answer text.
async def run_action_agent(request: str) -> str:
    """Run the Action Agent on a single request and return its answer."""

    # 1. Set up the LLM (Gemini via LangChain — swappable to any other model)
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=GOOGLE_API_KEY,
        temperature=0,
        max_output_tokens=1000,
    )

    # 2. Connect to the Action MCP server over HTTP (port 8002). The client
    #    discovers its tools at runtime and converts them into LangChain tools.
    client = MultiServerMCPClient(
        {
            "databricks-action": {
                "url": "http://127.0.0.1:8002/mcp",
                "transport": "streamable_http",
            }
        }
    )
    print("Connecting to Action MCP...")
    tools = await client.get_tools()

    # 3. Build a ReAct agent: it reasons about the request, calls a tool,
    #    reads the result, and reports back. LangGraph runs the loop.
    agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": request}]}
    )

    # The last message is the agent's final answer. Gemini returns content
    # as a list of blocks, so extract just the text.
    final_message = result["messages"][-1]
    content = final_message.content
    if isinstance(content, list):
        text_parts = [block.get("text", "") for block in content if isinstance(block, dict)]
        return "\n".join(text_parts).strip()
    return content


# Quick standalone test
if __name__ == "__main__":
    async def main():
        request = "Look up Tailspin Toys, then apply a billing correction to invoice INV016 setting the corrected amount to 2800, and open a billing dispute case for them about a discount not being applied."
        print(f"Request: {request}\n")
        answer = await run_action_agent(request)
        print(f"Answer:\n{answer}")

    asyncio.run(main())