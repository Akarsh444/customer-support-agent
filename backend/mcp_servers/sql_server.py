"""
SQL MCP Server
--------------
Exposes Databricks SQL data as MCP tools. Connects to Databricks
via databricks-sql-connector internally.
"""
import os
import sys
import datetime
import asyncio
import time
from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv
from databricks import sql
from fastmcp import FastMCP

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")
CATALOG = os.getenv("DATABRICKS_CATALOG", "workspace")
SCHEMA = os.getenv("DATABRICKS_SCHEMA", "support_agent")
GENIE_SPACE_ID = os.getenv("DATABRICKS_GENIE_SPACE_ID")

# --- File-based logging (NEVER print to stdout in an MCP stdio server) ---
LOG_PATH = os.path.join(os.path.dirname(__file__), "mcp_debug.log")

def log(msg: str):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now().isoformat()}  {msg}\n")

log("=== sql_server.py started ===")

mcp = FastMCP("databricks-sql-server")


def run_query(query: str, params: list) -> list[dict]:
    """Internal helper — synchronous blocking Databricks call."""
    log("run_query: entered")
    try:
        log("run_query: about to sql.connect")
        with sql.connect(
            server_hostname=DATABRICKS_HOST,
            http_path=DATABRICKS_HTTP_PATH,
            access_token=DATABRICKS_TOKEN,
        ) as connection:
            log("run_query: connected")
            with connection.cursor() as cursor:
                log("run_query: about to execute")
                cursor.execute(query, params)
                log("run_query: executed, about to fetchall")
                columns = [desc[0] for desc in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                log(f"run_query: fetched {len(rows)} rows, returning")
                return rows
    except Exception as e:
        log(f"run_query: EXCEPTION {type(e).__name__}: {e}")
        raise


@mcp.tool()
async def get_customer(customer_name: str) -> list[dict]:
    """
    Look up a customer by name. Returns customer details including
    plan, account status, and contact email. Supports partial matches.
    """
    log(f"get_customer: called with customer_name={customer_name}")
    query = f"""
        SELECT * FROM {CATALOG}.{SCHEMA}.customers
        WHERE LOWER(customer_name) LIKE LOWER(?)
    """
    return await asyncio.to_thread(run_query, query, [f"%{customer_name}%"])


@mcp.tool()
async def get_invoices(customer_name: str, month: str = None) -> list[dict]:
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
        return await asyncio.to_thread(run_query, query, [f"%{customer_name}%", month])
    query = f"""
        SELECT * FROM {CATALOG}.{SCHEMA}.invoices
        WHERE LOWER(customer_name) LIKE LOWER(?)
        ORDER BY month
    """
    return await asyncio.to_thread(run_query, query, [f"%{customer_name}%"])


@mcp.tool()
async def get_billing_issues() -> list[dict]:
    """
    Get all invoices flagged as Overbilled across all customers.
    Useful for finding billing problems and patterns.
    """
    query = f"""
        SELECT * FROM {CATALOG}.{SCHEMA}.invoices
        WHERE status = 'Overbilled'
    """
    return await asyncio.to_thread(run_query, query, [])

@mcp.tool()
async def ask_genie(question: str) -> dict:
    """
    Ask an open-ended natural-language question about customer billing,
    invoices, accounts, or support tickets. Use this for analytical or
    comparative questions that the specific tools cannot answer — for
    example: 'which customer had the most overbilling', 'average billed
    amount by plan', 'how many tickets are still open'. Genie converts
    the question to SQL and runs it against the support data.
    """
    log(f"ask_genie: called with question={question}")
    return await asyncio.to_thread(_run_genie, question)


def _run_genie(question: str) -> dict:
    """Internal helper — blocking Genie call via the Databricks SDK."""
    log("_run_genie: entered")

    # The SDK reads DATABRICKS_HOST and DATABRICKS_TOKEN from env automatically,
    # but we pass them explicitly to be safe.
    client = WorkspaceClient(
        host=f"https://{DATABRICKS_HOST}",
        token=DATABRICKS_TOKEN,
    )

    log("_run_genie: starting conversation")
    # Ask the question — this starts a Genie conversation and waits for completion.
    # create_message_and_wait handles the polling internally for us.
    conversation = client.genie.start_conversation_and_wait(
        space_id=GENIE_SPACE_ID,
        content=question,
    )

    log(f"_run_genie: got response, status complete")

    # Extract the text answer from Genie's response
    answer_text = ""
    if conversation.attachments:
        for attachment in conversation.attachments:
            if attachment.text:
                answer_text += attachment.text.content or ""

    # If Genie produced a SQL query + results, note that too
    result = {
        "answer": answer_text or "Genie returned no text answer.",
    }
    log(f"_run_genie: returning answer")
    return result


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8000)