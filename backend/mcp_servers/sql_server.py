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

# Create the MCP server. Tools registered below with @mcp.tool() are
# exposed to any agent that connects. The name is just an identifier.
mcp = FastMCP("databricks-sql-server")



# Runs a parameterised SQL query against Databricks and returns rows as
# a list of dicts (column name -> value). This is the ONLY place that
# actually touches Databricks. It is synchronous and blocking, so the
# async tools below call it via asyncio.to_thread (see note there).
# Parameters are passed separately (the `?` placeholders) — never string
# concatenation — to prevent SQL injection.

def run_query(query: str, params: list) -> list[dict]:
    """Internal helper — synchronous blocking Databricks call."""
    log("run_query: entered")

    # The log() calls trace execution step by step. They were added while
    # debugging a connection hang and are kept as diagnostics — if a
    # Databricks call ever stalls, mcp_debug.log shows how far it got.

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


# --- MCP TOOLS ---
# Each function below is exposed to the agent as a callable tool.
# The docstring is what the LLM reads to decide WHEN to use the tool,
# so it must clearly describe what the tool does. The function is async
# and offloads the blocking DB call to a thread so the server's event
# loop is never frozen (this was the fix for the earlier execution hang).

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


# Genie tool — for open-ended/analytical questions the fixed tools above
# can't answer. Instead of a pre-written query, it sends the natural-language
# question to Databricks Genie, which generates and runs the SQL itself.
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

# Internal helper for the Genie tool. Genie is asynchronous on Databricks'
# side — start_conversation_and_wait submits the question and blocks until
# Genie finishes generating SQL, running it, and returning an answer. The
# answer text lives inside the response's "attachments", which we extract below.
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

# Start the server over HTTP (not stdio). Running as a standalone web
# service on localhost:8000 keeps the Databricks connector in its own
# clean process — the stdio subprocess approach caused the connector to
# hang on Windows. The agent connects to this URL to discover and call tools.
if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8000)