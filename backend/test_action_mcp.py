"""
Isolated test for all four Action MCP tools.
Verifies each UC Function is callable through MCP before the agent.
"""
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient


async def main():
    client = MultiServerMCPClient(
        {"action": {"url": "http://127.0.0.1:8002/mcp", "transport": "streamable_http"}}
    )
    tools = await client.get_tools()
    print("Loaded:", [t.name for t in tools])

    t = {tool.name: tool for tool in tools}

    print("\n-- lookup_customer('Acme') --")
    print(await t["lookup_customer"].ainvoke({"customer_name": "Acme"}))

    print("\n-- apply_invoice_correction('INV016', 2800.0) --")
    print(await t["apply_invoice_correction"].ainvoke(
        {"invoice_id": "INV016", "corrected_amount": 2800.0}))

    print("\n-- create_case --")
    print(await t["create_case"].ainvoke({
        "customer_id": "C007", "customer_name": "Contoso Ltd",
        "issue_type": "Billing Dispute", "description": "Late fee applied in error"}))

    print("\n-- update_account_status('C015', 'Active') --")
    print(await t["update_account_status"].ainvoke(
        {"customer_id": "C015", "new_status": "Active"}))


asyncio.run(main())