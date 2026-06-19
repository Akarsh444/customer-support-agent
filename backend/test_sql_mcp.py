import asyncio
import os
from langchain_mcp_adapters.client import MultiServerMCPClient

SQL_SERVER = os.path.join(
    os.path.dirname(__file__),
    "mcp_servers",
    "sql_server.py"
)

async def main():
    client = MultiServerMCPClient(
        {
            "sql": {
                "command": r"C:\customer-support-agent\backend\venv311\Scripts\python.exe",
                "args": [SQL_SERVER],
                "transport": "stdio",
            }
        }
    )

    print("Loading tools...")
    tools = await client.get_tools()

    print("Loaded:", [t.name for t in tools])

    print("Calling get_customer...")

    result = await asyncio.wait_for(
        tools[0].ainvoke({"customer_name": "Acme"}),
        timeout=30
    )

    print(result)

asyncio.run(main())