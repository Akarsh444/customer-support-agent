"""
Action MCP Server
-----------------
Exposes Unity Catalog Functions as MCP tools for the Action Agent.
Performs deterministic operations — customer lookup and case creation —
by calling the UC Functions registered in Databricks. Runs over HTTP
on port 8002 (the SQL MCP server uses 8000).
"""
import os
import datetime
import asyncio
from dotenv import load_dotenv
from databricks import sql
from fastmcp import FastMCP

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")
CATALOG = os.getenv("DATABRICKS_CATALOG", "workspace")
SCHEMA = os.getenv("DATABRICKS_SCHEMA", "support_agent")

# File-based logging (never print to stdout from an MCP server)
LOG_PATH = os.path.join(os.path.dirname(__file__), "action_debug.log")

def log(msg: str):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now().isoformat()}  {msg}\n")

log("=== action_server.py started ===")

# Create the MCP server. Tools below are exposed to the Action Agent.
mcp = FastMCP("databricks-action-server")


# Runs a SQL statement against Databricks and returns rows as dicts.
# Same blocking-call pattern as the SQL server; the async tools offload
# to a thread so the event loop is never frozen. This is the only place
# that touches Databricks.
def run_query(query: str, params: list) -> list[dict]:
    log("run_query: entered")
    try:
        with sql.connect(
            server_hostname=DATABRICKS_HOST,
            http_path=DATABRICKS_HTTP_PATH,
            access_token=DATABRICKS_TOKEN,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                columns = [desc[0] for desc in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                log(f"run_query: fetched {len(rows)} rows")
                return rows
    except Exception as e:
        log(f"run_query: EXCEPTION {type(e).__name__}: {e}")
        raise


# --- MCP TOOLS (each calls a Unity Catalog Function) ---

@mcp.tool()
async def lookup_customer(customer_name: str) -> list[dict]:
    """
    Look up a customer account by name. Returns the customer's id, plan,
    account status, and contact email. Use this to find a customer's
    account details before performing an action on their account.
    """
    log(f"lookup_customer: called with customer_name={customer_name}")
    query = f"SELECT * FROM {CATALOG}.{SCHEMA}.lookup_customer(?)"
    return await asyncio.to_thread(run_query, query, [customer_name])


@mcp.tool()
async def apply_invoice_correction(invoice_id: str, corrected_amount: float) -> dict:
    """
    Apply a billing correction to an overbilled invoice. Sets the invoice's
    billed amount to the corrected value and marks it 'Corrected'. Use this
    to actually resolve an overbilling — it changes the invoice record.
    """
    log(f"apply_invoice_correction: invoice={invoice_id} amount={corrected_amount}")
    query = f"SELECT {CATALOG}.{SCHEMA}.apply_invoice_correction(?, ?) AS result"
    rows = await asyncio.to_thread(run_query, query, [invoice_id, corrected_amount])
    return {"result": rows[0]["result"] if rows else "No result."}


@mcp.tool()
async def create_case(
    customer_id: str,
    customer_name: str,
    issue_type: str,
    description: str,
) -> dict:
    """
    Create a new support case for a customer. Inserts a real ticket into
    the support system and returns the new ticket ID. Use this when a
    customer needs a support case opened (e.g. a billing dispute).
    """
    log(f"create_case: called for {customer_name} ({customer_id})")
    query = f"SELECT {CATALOG}.{SCHEMA}.create_case(?, ?, ?, ?) AS result"
    rows = await asyncio.to_thread(
        run_query, query, [customer_id, customer_name, issue_type, description]
    )
    return {"result": rows[0]["result"] if rows else "No result."}


@mcp.tool()
async def update_account_status(customer_id: str, new_status: str) -> dict:
    """
    Update a customer's account status (for example 'Active' or 'Suspended').
    Use this to change a customer's account standing. It changes the
    customer record.
    """
    log(f"update_account_status: customer={customer_id} status={new_status}")
    query = f"SELECT {CATALOG}.{SCHEMA}.update_account_status(?, ?) AS result"
    rows = await asyncio.to_thread(run_query, query, [customer_id, new_status])
    return {"result": rows[0]["result"] if rows else "No result."}


# Start the server over HTTP on port 8002 (SQL MCP server is on 8000).
# The Action Agent connects to this URL to discover and call the tools.
if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8002)