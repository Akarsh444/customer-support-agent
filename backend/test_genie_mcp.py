"""
Isolated test for the ask_genie MCP tool.
Calls Genie directly through MCP — no agent, no Gemini.
Proves Genie works end-to-end before wiring it into the Data Agent.
"""
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient


async def main():
    client = MultiServerMCPClient(
        {
            "sql": {
                "url": "http://127.0.0.1:8000/mcp",
                "transport": "streamable_http",
            }
        }
    )

    print("Loading tools...")
    tools = await client.get_tools()
    print("Loaded:", [t.name for t in tools])

    # Find the ask_genie tool specifically
    genie_tool = next(t for t in tools if t.name == "ask_genie")

    print("\nAsking Genie a question the fixed tools can't answer...")
    print("Question: Which customer had the largest overbilling?\n")

    result = await asyncio.wait_for(
        genie_tool.ainvoke({"question": "Which customer had the largest overbilling?"}),
        timeout=120  # Genie is slow — give it 2 minutes
    )

    print("Genie's answer:")
    print(result)


asyncio.run(main())