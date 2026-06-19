"""Quick test of the SQL MCP server's tool logic (direct call, no MCP yet)."""
from mcp_servers.sql_server import get_customer, get_invoices, get_billing_issues

print("--- get_customer('Acme') ---")
print(get_customer("Acme"))

print("\n--- get_invoices('Acme', 'May 2025') ---")
print(get_invoices("Acme", "May 2025"))

print("\n--- get_billing_issues() ---")
print(get_billing_issues())