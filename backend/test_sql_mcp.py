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

    print("Calling get_customer...")
    result = await asyncio.wait_for(
        tools[0].ainvoke({"customer_name": "Acme"}),
        timeout=120
    )
    print(result)

asyncio.run(main())