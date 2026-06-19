"""
Test script — verifies we can connect to Databricks SQL
and query our tables. Run this before anything else.
"""
import os
from dotenv import load_dotenv
from databricks import sql

# Load credentials from .env (one folder up from backend/)
load_dotenv(dotenv_path="../.env")

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")

print(f"Connecting to: {DATABRICKS_HOST}")

connection = sql.connect(
    server_hostname=DATABRICKS_HOST,
    http_path=DATABRICKS_HTTP_PATH,
    access_token=DATABRICKS_TOKEN,
)

cursor = connection.cursor()
cursor.execute("SELECT * FROM workspace.support_agent.customers LIMIT 5")

rows = cursor.fetchall()
print(f"\nConnection successful! Found {len(rows)} customers:\n")
for row in rows:
    print(f"  {row.customer_id} | {row.customer_name} | {row.plan} | {row.account_status}")

cursor.close()
connection.close()
print("\nDone.")