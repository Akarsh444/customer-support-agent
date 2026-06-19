"""
SQL MCP Server
--------------
Exposes Databricks SQL data (customers, invoices) as MCP tools.
The Data Agent calls these tools via the MCP protocol — it never
touches Databricks directly. The databricks-sql-connector is an
internal implementation detail of this server.
"""
import os
from dotenv import load_dotenv
from databricks import sql
from fastmcp import FastMCP

# .env lives two levels up from this file (project root)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")
CATALOG = os.getenv("DATABRICKS_CATALOG", "workspace")
SCHEMA = os.getenv("DATABRICKS_SCHEMA", "support_agent")

mcp = FastMCP("databricks-sql-server")


def run_query(query: str, params: list) -> list[dict]:
    """Internal helper — runs a parameterised query and returns rows as dicts."""
    with sql.connect(
        server_hostname=DATABRICKS_HOST,
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_TOKEN,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


@mcp.tool()
def get_customer(customer_name: str) -> list[dict]:
    """
    Look up a customer by name. Returns customer details including
    plan, account status, and contact email. Supports partial matches.
    """
    query = f"""
        SELECT * FROM {CATALOG}.{SCHEMA}.customers
        WHERE LOWER(customer_name) LIKE LOWER(?)
    """
    return run_query(query, [f"%{customer_name}%"])


@mcp.tool()
def get_invoices(customer_name: str, month: str = None) -> list[dict]:
    """
    Get invoices for a customer. Optionally filter by month
    (e.g. 'May 2025'). Returns billed amount, expected amount,
    status (Correct/Overbilled), and the issue reason if any.
    """
    if month:
        query = f"""
            SELECT * FROM {CATALOG}.{SCHEMA}.invoices
            WHERE LOWER(customer_name) LIKE LOWER(?)
            AND LOWER(month) = LOWER(?)
        """
        return run_query(query, [f"%{customer_name}%", month])
    query = f"""
        SELECT * FROM {CATALOG}.{SCHEMA}.invoices
        WHERE LOWER(customer_name) LIKE LOWER(?)
        ORDER BY month
    """
    return run_query(query, [f"%{customer_name}%"])


@mcp.tool()
def get_billing_issues() -> list[dict]:
    """
    Get all invoices flagged as Overbilled across all customers.
    Useful for finding billing problems and patterns.
    """
    query = f"""
        SELECT * FROM {CATALOG}.{SCHEMA}.invoices
        WHERE status = 'Overbilled'
    """
    return run_query(query, [])


if __name__ == "__main__":
    mcp.run()