import ast
import difflib
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import dotenv
import numpy as np
import pandas as pd
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits
from sqlalchemy import Engine, create_engine
from sqlalchemy.sql import text
import re

# Load environment variables from .env
dotenv.load_dotenv()

# Create an SQLite database engine
db_engine = create_engine("sqlite:///munder_difflin.db")

# List containing the different kinds of papers
paper_supplies = [
    # Paper Types (priced per sheet unless specified)
    {"item_name": "A4 paper", "category": "paper", "unit_price": 0.05},
    {"item_name": "Letter-sized paper", "category": "paper", "unit_price": 0.06},
    {"item_name": "Cardstock", "category": "paper", "unit_price": 0.15},
    {"item_name": "Colored paper", "category": "paper", "unit_price": 0.10},
    {"item_name": "Glossy paper", "category": "paper", "unit_price": 0.20},
    {"item_name": "Matte paper", "category": "paper", "unit_price": 0.18},
    {"item_name": "Recycled paper", "category": "paper", "unit_price": 0.08},
    {"item_name": "Eco-friendly paper", "category": "paper", "unit_price": 0.12},
    {"item_name": "Poster paper", "category": "paper", "unit_price": 0.25},
    {"item_name": "Banner paper", "category": "paper", "unit_price": 0.30},
    {"item_name": "Kraft paper", "category": "paper", "unit_price": 0.10},
    {"item_name": "Construction paper", "category": "paper", "unit_price": 0.07},
    {"item_name": "Wrapping paper", "category": "paper", "unit_price": 0.15},
    {"item_name": "Glitter paper", "category": "paper", "unit_price": 0.22},
    {"item_name": "Decorative paper", "category": "paper", "unit_price": 0.18},
    {"item_name": "Letterhead paper", "category": "paper", "unit_price": 0.12},
    {"item_name": "Legal-size paper", "category": "paper", "unit_price": 0.08},
    {"item_name": "Crepe paper", "category": "paper", "unit_price": 0.05},
    {"item_name": "Photo paper", "category": "paper", "unit_price": 0.25},
    {"item_name": "Uncoated paper", "category": "paper", "unit_price": 0.06},
    {"item_name": "Butcher paper", "category": "paper", "unit_price": 0.10},
    {"item_name": "Heavyweight paper", "category": "paper", "unit_price": 0.20},
    {"item_name": "Standard copy paper", "category": "paper", "unit_price": 0.04},
    {"item_name": "Bright-colored paper", "category": "paper", "unit_price": 0.12},
    {"item_name": "Patterned paper", "category": "paper", "unit_price": 0.15},

    # Product Types (priced per unit)
    {"item_name": "Paper plates", "category": "product", "unit_price": 0.10},
    {"item_name": "Paper cups", "category": "product", "unit_price": 0.08},
    {"item_name": "Paper napkins", "category": "product", "unit_price": 0.02},
    {"item_name": "Disposable cups", "category": "product", "unit_price": 0.10},
    {"item_name": "Table covers", "category": "product", "unit_price": 1.50},
    {"item_name": "Envelopes", "category": "product", "unit_price": 0.05},
    {"item_name": "Sticky notes", "category": "product", "unit_price": 0.03},
    {"item_name": "Notepads", "category": "product", "unit_price": 2.00},
    {"item_name": "Invitation cards", "category": "product", "unit_price": 0.50},
    {"item_name": "Flyers", "category": "product", "unit_price": 0.15},
    {"item_name": "Party streamers", "category": "product", "unit_price": 0.05},
    {"item_name": "Decorative adhesive tape (washi tape)", "category": "product", "unit_price": 0.20},
    {"item_name": "Paper party bags", "category": "product", "unit_price": 0.25},
    {"item_name": "Name tags with lanyards", "category": "product", "unit_price": 0.75},
    {"item_name": "Presentation folders", "category": "product", "unit_price": 0.50},

    # Large-format items (priced per unit)
    {"item_name": "Large poster paper (24x36 inches)", "category": "large_format", "unit_price": 1.00},
    {"item_name": "Rolls of banner paper (36-inch width)", "category": "large_format", "unit_price": 2.50},

    # Specialty papers
    {"item_name": "100 lb cover stock", "category": "specialty", "unit_price": 0.50},
    {"item_name": "80 lb text paper", "category": "specialty", "unit_price": 0.40},
    {"item_name": "250 gsm cardstock", "category": "specialty", "unit_price": 0.30},
    {"item_name": "220 gsm poster paper", "category": "specialty", "unit_price": 0.35},
]

# Fast lookup dictionary for catalog unit prices
CATALOG_PRICES: Dict[str, float] = {
    item["item_name"]: item["unit_price"] for item in paper_supplies
}

# Mapping of common customer phrases/modifiers to exact database item_name strings
ITEM_ALIASES: Dict[str, str] = {
    "a4 glossy paper": "Glossy paper",
    "glossy a4 paper": "Glossy paper",
    "high-quality glossy paper": "Glossy paper",
    "a3 glossy paper": "Glossy paper",
    "a4 matte paper": "Matte paper",
    "matte a3 paper": "Matte paper",
    "a3 matte paper": "Matte paper",
    "a4 white paper": "A4 paper",
    "a4 white printer paper": "A4 paper",
    "a4 printer paper": "A4 paper",
    "a4 printing paper": "A4 paper",
    "a4 size printer paper": "A4 paper",
    "a4 paper": "A4 paper",
    "standard printer paper": "Standard copy paper",
    "standard printing paper": "Standard copy paper",
    "printer paper": "Standard copy paper",
    "white printer paper": "Standard copy paper",
    "copy paper": "Standard copy paper",
    "a3 paper": "Colored paper",
    "a3 colored paper": "Colored paper",
    "a5 colored paper": "Colored paper",
    "8.5x11 colored paper": "Colored paper",
    "8.5\"x11\" colored paper": "Colored paper",
    "colored paper (assorted colors)": "Colored paper",
    "colorful paper": "Colored paper",
    "a4 recycled paper": "Recycled paper",
    "recycled paper": "Recycled paper",
    "heavy cardstock": "Cardstock",
    "heavy cardstock (white)": "Cardstock",
    "heavyweight cardstock": "Cardstock",
    "high-quality white cardstock": "Cardstock",
    "high-quality recycled cardstock": "Cardstock",
    "recycled cardstock": "Cardstock",
    "colorful cardstock": "Cardstock",
    "cardstock in various colors": "Cardstock",
    "cardstock in assorted colors": "Cardstock",
    "sturdy cardstock": "Cardstock",
    "white cardstock": "Cardstock",
    "cardstock": "Cardstock",
    "colorful poster paper": "Poster paper",
    "poster paper in various colors": "Poster paper",
    "poster board": "Poster paper",
    "poster boards": "Large poster paper (24x36 inches)",
    "poster boards (24 x 36)": "Large poster paper (24x36 inches)",
    "poster boards (24\" x 36\")": "Large poster paper (24x36 inches)",
    "posters": "Poster paper",
    "colorful construction paper": "Construction paper",
    "streamers": "Party streamers",
    "roll of streamers": "Party streamers",
    "decorative washi tape": "Decorative adhesive tape (washi tape)",
    "washi tape": "Decorative adhesive tape (washi tape)",
    "table napkins": "Paper napkins",
    "table napkins (white)": "Paper napkins",
    "white napkins": "Paper napkins",
    "paper cups (biodegradable)": "Paper cups",
    "paper plates (biodegradable)": "Paper plates",
    "kraft paper envelopes": "Envelopes",
    "100% recycled kraft paper envelopes": "Envelopes",
    "flyers": "Flyers",
}


def resolve_catalog_item(query_name: str) -> Optional[str]:
    """
    Resolve an informal customer item description to an exact item_name in `paper_supplies`.
    Returns None if the requested item is not carried in Munder Difflin's catalog.
    """
    if not query_name:
        return None

    cleaned = query_name.strip().lower()

    # Explicitly reject items Munder Difflin does not carry
    non_catalog_keywords = ("balloon", "cardboard", "ticket", "lanyard only", "plastic")
    if any(kw in cleaned for kw in non_catalog_keywords):
        return None

    # 1. Exact case-insensitive match against official catalog
    for item_name in CATALOG_PRICES:
        if item_name.lower() == cleaned:
            return item_name

    # 2. Direct lookup in ITEM_ALIASES
    if cleaned in ITEM_ALIASES:
        return ITEM_ALIASES[cleaned]

    # 3. Strip parenthetical notes like "(assorted colors)" or "(white)" and retry
    base_name = cleaned.split("(")[0].strip()
    for item_name in CATALOG_PRICES:
        if item_name.lower() == base_name:
            return item_name
    if base_name in ITEM_ALIASES:
        return ITEM_ALIASES[base_name]

    # 4. High-confidence fuzzy match against official catalog names
    catalog_lower = {k.lower(): k for k in CATALOG_PRICES}
    matches = difflib.get_close_matches(base_name, list(catalog_lower.keys()), n=1, cutoff=0.78)
    if matches:
        return catalog_lower[matches[0]]

    return None


# ==============================================================================
# STARTER DATABASE & UTILITY FUNCTIONS
# ==============================================================================

def generate_sample_inventory(
    paper_supplies: list, coverage: float = 0.4, seed: int = 137
) -> pd.DataFrame:
    """
    Generate inventory for exactly a specified percentage of items from the full paper supply list.
    """
    np.random.seed(seed)
    num_items = int(len(paper_supplies) * coverage)
    selected_indices = np.random.choice(
        range(len(paper_supplies)), size=num_items, replace=False
    )
    selected_items = [paper_supplies[i] for i in selected_indices]

    inventory = []
    for item in selected_items:
        inventory.append(
            {
                "item_name": item["item_name"],
                "category": item["category"],
                "unit_price": item["unit_price"],
                "current_stock": np.random.randint(200, 800),
                "min_stock_level": np.random.randint(50, 150),
            }
        )
    return pd.DataFrame(inventory)


def init_database(db_engine: Engine, seed: int = 137) -> Engine:
    """
    Set up the Munder Difflin database with all required tables and initial records.
    """
    try:
        transactions_schema = pd.DataFrame(
            {
                "id": [],
                "item_name": [],
                "transaction_type": [],
                "units": [],
                "price": [],
                "transaction_date": [],
            }
        )
        transactions_schema.to_sql(
            "transactions", db_engine, if_exists="replace", index=False
        )

        initial_date = datetime(2025, 1, 1).isoformat()

        quote_requests_df = pd.read_csv("quote_requests.csv")
        quote_requests_df["id"] = range(1, len(quote_requests_df) + 1)
        quote_requests_df.to_sql(
            "quote_requests", db_engine, if_exists="replace", index=False
        )

        quotes_df = pd.read_csv("quotes.csv")
        quotes_df["request_id"] = range(1, len(quotes_df) + 1)
        quotes_df["order_date"] = initial_date

        if "request_metadata" in quotes_df.columns:
            quotes_df["request_metadata"] = quotes_df["request_metadata"].apply(
                lambda x: ast.literal_eval(x) if isinstance(x, str) else x
            )
            quotes_df["job_type"] = quotes_df["request_metadata"].apply(
                lambda x: x.get("job_type", "")
            )
            quotes_df["order_size"] = quotes_df["request_metadata"].apply(
                lambda x: x.get("order_size", "")
            )
            quotes_df["event_type"] = quotes_df["request_metadata"].apply(
                lambda x: x.get("event_type", "")
            )

        quotes_df = quotes_df[
            [
                "request_id",
                "total_amount",
                "quote_explanation",
                "order_date",
                "job_type",
                "order_size",
                "event_type",
            ]
        ]
        quotes_df.to_sql("quotes", db_engine, if_exists="replace", index=False)

        inventory_df = generate_sample_inventory(paper_supplies, seed=seed)

        initial_transactions = [
            {
                "item_name": None,
                "transaction_type": "sales",
                "units": None,
                "price": 50000.0,
                "transaction_date": initial_date,
            }
        ]

        for _, item in inventory_df.iterrows():
            initial_transactions.append(
                {
                    "item_name": item["item_name"],
                    "transaction_type": "stock_orders",
                    "units": item["current_stock"],
                    "price": item["current_stock"] * item["unit_price"],
                    "transaction_date": initial_date,
                }
            )

        pd.DataFrame(initial_transactions).to_sql(
            "transactions", db_engine, if_exists="append", index=False
        )
        inventory_df.to_sql("inventory", db_engine, if_exists="replace", index=False)

        return db_engine

    except Exception as e:
        print(f"Error initializing database: {e}")
        raise


def create_transaction(
    item_name: str,
    transaction_type: str,
    quantity: int,
    price: float,
    date: Union[str, datetime],
) -> int:
    """
    Record a transaction of type 'stock_orders' or 'sales' into the 'transactions' table.
    """
    try:
        date_str = date.isoformat() if isinstance(date, datetime) else date
        if transaction_type not in {"stock_orders", "sales"}:
            raise ValueError("Transaction type must be 'stock_orders' or 'sales'")

        transaction = pd.DataFrame(
            [
                {
                    "item_name": item_name,
                    "transaction_type": transaction_type,
                    "units": quantity,
                    "price": price,
                    "transaction_date": date_str,
                }
            ]
        )

        transaction.to_sql("transactions", db_engine, if_exists="append", index=False)
        result = pd.read_sql("SELECT last_insert_rowid() as id", db_engine)
        return int(result.iloc[0]["id"])

    except Exception as e:
        print(f"Error creating transaction: {e}")
        raise


def get_all_inventory(as_of_date: str) -> Dict[str, int]:
    """
    Retrieve a snapshot of available inventory as of a specific date.
    """
    query = """
        SELECT
            item_name,
            SUM(CASE
                WHEN transaction_type = 'stock_orders' THEN units
                WHEN transaction_type = 'sales' THEN -units
                ELSE 0
            END) as stock
        FROM transactions
        WHERE item_name IS NOT NULL
        AND transaction_date <= :as_of_date
        GROUP BY item_name
        HAVING stock > 0
    """
    result = pd.read_sql(query, db_engine, params={"as_of_date": as_of_date})
    return dict(zip(result["item_name"], result["stock"]))


def get_stock_level(item_name: str, as_of_date: Union[str, datetime]) -> pd.DataFrame:
    """
    Retrieve the stock level of a specific item as of a given date.
    """
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()

    stock_query = """
        SELECT
            item_name,
            COALESCE(SUM(CASE
                WHEN transaction_type = 'stock_orders' THEN units
                WHEN transaction_type = 'sales' THEN -units
                ELSE 0
            END), 0) AS current_stock
        FROM transactions
        WHERE item_name = :item_name
        AND transaction_date <= :as_of_date
    """
    return pd.read_sql(
        stock_query,
        db_engine,
        params={"item_name": item_name, "as_of_date": as_of_date},
    )


def get_supplier_delivery_date(input_date_str: str, quantity: int) -> str:
    """
    Estimate the supplier delivery date based on the requested order quantity and a starting date.
    """
    print(
        f"FUNC (get_supplier_delivery_date): Calculating for qty {quantity} from date string '{input_date_str}'"
    )
    try:
        input_date_dt = datetime.fromisoformat(input_date_str.split("T")[0])
    except (ValueError, TypeError):
        print(
            f"WARN (get_supplier_delivery_date): Invalid date format '{input_date_str}', using today as base."
        )
        input_date_dt = datetime.now()

    if quantity <= 10:
        days = 0
    elif quantity <= 100:
        days = 1
    elif quantity <= 1000:
        days = 4
    else:
        days = 7

    delivery_date_dt = input_date_dt + timedelta(days=days)
    return delivery_date_dt.strftime("%Y-%m-%d")


def get_cash_balance(as_of_date: Union[str, datetime]) -> float:
    """
    Calculate the current cash balance as of a specified date.
    """
    try:
        if isinstance(as_of_date, datetime):
            as_of_date = as_of_date.isoformat()

        transactions = pd.read_sql(
            "SELECT * FROM transactions WHERE transaction_date <= :as_of_date",
            db_engine,
            params={"as_of_date": as_of_date},
        )

        if not transactions.empty:
            total_sales = transactions.loc[
                transactions["transaction_type"] == "sales", "price"
            ].sum()
            total_purchases = transactions.loc[
                transactions["transaction_type"] == "stock_orders", "price"
            ].sum()
            return float(total_sales - total_purchases)

        return 0.0

    except Exception as e:
        print(f"Error getting cash balance: {e}")
        return 0.0


def generate_financial_report(as_of_date: Union[str, datetime]) -> Dict:
    """
    Generate a complete financial report for the company as of a specific date.
    """
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()

    cash = get_cash_balance(as_of_date)
    inventory_df = pd.read_sql("SELECT * FROM inventory", db_engine)
    inventory_value = 0.0
    inventory_summary = []

    for _, item in inventory_df.iterrows():
        stock_info = get_stock_level(item["item_name"], as_of_date)
        stock = stock_info["current_stock"].iloc[0]
        item_value = stock * item["unit_price"]
        inventory_value += item_value

        inventory_summary.append(
            {
                "item_name": item["item_name"],
                "stock": stock,
                "unit_price": item["unit_price"],
                "value": item_value,
            }
        )

    top_sales_query = """
        SELECT item_name, SUM(units) as total_units, SUM(price) as total_revenue
        FROM transactions
        WHERE transaction_type = 'sales' AND transaction_date <= :date
        GROUP BY item_name
        ORDER BY total_revenue DESC
        LIMIT 5
    """
    top_sales = pd.read_sql(top_sales_query, db_engine, params={"date": as_of_date})
    top_selling_products = top_sales.to_dict(orient="records")

    return {
        "as_of_date": as_of_date,
        "cash_balance": cash,
        "inventory_value": inventory_value,
        "total_assets": cash + inventory_value,
        "inventory_summary": inventory_summary,
        "top_selling_products": top_selling_products,
    }


def search_quote_history(search_terms: List[str], limit: int = 5) -> List[Dict]:
    """
    Retrieve a list of historical quotes that match any of the provided search terms.
    """
    conditions = []
    params = {}

    for i, term in enumerate(search_terms):
        param_name = f"term_{i}"
        conditions.append(
            f"(LOWER(qr.response) LIKE :{param_name} OR "
            f"LOWER(q.quote_explanation) LIKE :{param_name})"
        )
        params[param_name] = f"%{term.lower()}%"

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    query = f"""
        SELECT
            qr.response AS original_request,
            q.total_amount,
            q.quote_explanation,
            q.job_type,
            q.order_size,
            q.event_type,
            q.order_date
        FROM quotes q
        JOIN quote_requests qr ON q.request_id = qr.id
        WHERE {where_clause}
        ORDER BY q.order_date DESC
        LIMIT {limit}
    """

    with db_engine.connect() as conn:
        result = conn.execute(text(query), params)
        return [dict(row._mapping) for row in result]


########################
########################
########################
# YOUR MULTI AGENT STARTS HERE
########################
########################
########################

# Configure LLM model via Vocareum OpenAI-compatible proxy
api_key = os.getenv("UDACITY_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
provider = OpenAIProvider(
    base_url="https://openai.vocareum.com/v1",
    api_key=api_key,
)
llm_model = OpenAIChatModel("gpt-4o-mini", provider=provider)


# ==============================================================================
# AGENT 2: INVENTORY & PROCUREMENT AGENT
# ==============================================================================

inventory_agent = Agent(
    llm_model,
    name="inventory_agent",
    instructions=(
        "You are the Inventory & Procurement Specialist at Munder Difflin Paper Company. "
        "Your responsibility is to check inventory levels, verify supplier delivery lead times, "
        "and reorder stock when needed. "
        "CRITICAL ANTI-LOOP RULES: "
        "1. Call `check_item_stock` ONCE per requested item. It uses `resolve_catalog_item` to map "
        "customer phrasing to exact catalog names. "
        "2. If `check_item_stock` reports an item is NOT in the catalog, immediately mark it as UNFULFILLABLE "
        "and do NOT retry or search repeatedly. "
        "3. If stock is below the requested quantity, call `check_supplier_timeline` once. "
        "If the supplier ETA is on or before the customer's deadline, call `reorder_stock` once to replenish "
        "enough units (shortfall + 200 buffer) so the order can be fulfilled. "
        "If the supplier ETA is AFTER the customer's deadline, do NOT reorder; immediately report the item "
        "as UNFULFILLABLE due to delivery timeline constraints. "
        "4. Never reveal internal company cash balances in your summary."
    ),
)


@inventory_agent.tool_plain
def list_available_inventory(as_of_date: str) -> str:
    """Return a snapshot of all currently stocked catalog items as of `as_of_date` (YYYY-MM-DD)."""
    inv = get_all_inventory(as_of_date)
    if not inv:
        return "No items currently have positive stock."
    lines = [f"- {name}: {qty} units" for name, qty in sorted(inv.items())]
    return "Current positive inventory: " + " ".join(lines)


@inventory_agent.tool_plain
def check_item_stock(item_description: str, as_of_date: str) -> str:
    """
    Resolve `item_description` to an official catalog item via `resolve_catalog_item`
    and check its current stock level as of `as_of_date` (YYYY-MM-DD).
    """
    catalog_name = resolve_catalog_item(item_description)
    if not catalog_name:
        return (
            f"UNAVAILABLE: '{item_description}' is not carried in Munder Difflin's catalog."
        )

    df = get_stock_level(catalog_name, as_of_date)
    stock = int(df["current_stock"].iloc[0]) if not df.empty else 0
    unit_price = CATALOG_PRICES.get(catalog_name, 0.0)
    return (
        f"CATALOG_ITEM: '{catalog_name}' | Current Stock: {stock} units | "
        f"Standard Unit Price: ${unit_price:.2f}"
    )


@inventory_agent.tool_plain
def check_supplier_timeline(request_date: str, reorder_quantity: int) -> str:
    """Check the estimated supplier delivery date (YYYY-MM-DD) for `reorder_quantity` units."""
    eta = get_supplier_delivery_date(request_date, reorder_quantity)
    return f"Estimated supplier arrival date for {reorder_quantity} units ordered on {request_date}: {eta}"


@inventory_agent.tool_plain
def reorder_stock(
    item_description: str,
    quantity_needed: int,
    request_date: str,
    customer_deadline: str,
) -> str:
    """
    Place a supplier restock order (`stock_orders`) if the supplier delivery ETA meets
    `customer_deadline` and the company has sufficient cash balance.
    """
    catalog_name = resolve_catalog_item(item_description)
    if not catalog_name:
        return f"RESTOCK_FAILED: '{item_description}' is not in the catalog."

    eta = get_supplier_delivery_date(request_date, quantity_needed)
    if customer_deadline and eta > customer_deadline:
        return (
            f"RESTOCK_SKIPPED: Supplier delivery ETA ({eta}) exceeds customer deadline ({customer_deadline})."
        )

    unit_cost = CATALOG_PRICES[catalog_name] * 0.60  # Wholesale supplier cost (60% of retail)
    total_cost = round(quantity_needed * unit_cost, 2)
    available_cash = get_cash_balance(request_date)

    if available_cash < total_cost:
        return (
            f"RESTOCK_FAILED: Insufficient supply procurement capacity for {quantity_needed} units of {catalog_name}."
        )

    tx_id = create_transaction(
        item_name=catalog_name,
        transaction_type="stock_orders",
        quantity=quantity_needed,
        price=total_cost,
        date=request_date,
    )
    return (
        f"RESTOCK_SUCCESS: Ordered {quantity_needed} units of '{catalog_name}' "
        f"(Transaction #{tx_id}). Supplier ETA: {eta}."
    )


# ==============================================================================
# AGENT 3: QUOTING & PRICING AGENT
# ==============================================================================

quoting_agent = Agent(
    llm_model,
    name="quoting_agent",
    instructions=(
        "You are the Quoting & Pricing Specialist at Munder Difflin Paper Company. "
        "Your job is to generate competitive, transparent quotes using historical quote benchmarks "
        "and tiered bulk discounts. "
        "CRITICAL ANTI-LOOP RULES: "
        "1. Call `lookup_past_quotes` ONCE using 1-2 relevant keywords (such as event type or paper type). "
        "2. Call `calculate_bulk_quote` ONCE with a comma-separated list of `item_name:quantity` pairs. "
        "3. Return a clear itemized breakdown showing unit prices, subtotal, bulk discount percentage, "
        "and final rounded total."
    ),
)


@quoting_agent.tool_plain
def lookup_past_quotes(keywords: str) -> str:
    """Search historical quotes matching comma-separated `keywords` for pricing and discount context."""
    terms = [t.strip() for t in keywords.split(",") if t.strip()]
    matches = search_quote_history(terms, limit=3)
    if not matches:
        return "No close historical quotes found; apply standard tiered bulk discount rules."
    summaries = []
    for m in matches:
        summaries.append(
            f"- Event: {m.get('event_type')}, Size: {m.get('order_size')}, "
            f"Total: ${m.get('total_amount')}, Notes: {str(m.get('quote_explanation', ''))[:160]}..."
        )
    return "Historical quote benchmarks: " + " ".join(summaries)


@quoting_agent.tool_plain
def calculate_bulk_quote(items_and_quantities: str) -> str:
    """
    Calculate an itemized quote with tiered bulk discounts.
    `items_and_quantities` format: 'A4 paper:500, Cardstock:200'
    """
    line_items = []
    subtotal = 0.0
    total_units = 0

    for entry in items_and_quantities.split(","):
        if ":" not in entry:
            continue
        raw_name, raw_qty = entry.split(":", 1)
        catalog_name = resolve_catalog_item(raw_name.strip())
        try:
            qty = int(float(raw_qty.strip()))
        except ValueError:
            continue

        if not catalog_name or qty <= 0:
            line_items.append(f"- {raw_name.strip()}: Not available in catalog")
            continue

        unit_price = CATALOG_PRICES[catalog_name]
        line_total = qty * unit_price
        subtotal += line_total
        total_units += qty
        line_items.append(
            f"- {catalog_name}: {qty} units @ ${unit_price:.2f}/unit = ${line_total:.2f}"
        )

    if total_units == 0:
        return "QUOTE_EMPTY: No valid catalog items could be priced."

    # Tiered bulk discount schedule
    if total_units >= 5000:
        discount_rate = 0.15
        tier_label = "15% Enterprise Bulk Discount (5,000+ units)"
    elif total_units >= 1000:
        discount_rate = 0.10
        tier_label = "10% Large Bulk Discount (1,000-4,999 units)"
    elif total_units >= 500:
        discount_rate = 0.05
        tier_label = "5% Standard Bulk Discount (500-999 units)"
    else:
        discount_rate = 0.0
        tier_label = "Standard Pricing (under 500 units)"

    discount_amount = round(subtotal * discount_rate, 2)
    final_total = round(subtotal - discount_amount, 2)

    return (
        "ITEMIZED QUOTE: "
        + " ".join(line_items)
        + f"Subtotal: ${subtotal:.2f}"
        + f"Discount ({tier_label}): -${discount_amount:.2f}"
        + f"Final Quoted Total: ${final_total:.2f}"
    )


# ==============================================================================
# AGENT 4: SALES & FULFILLMENT AGENT
# ==============================================================================

sales_agent = Agent(
    llm_model,
    name="sales_agent",
    instructions=(
        "You are the Sales & Fulfillment Specialist at Munder Difflin Paper Company. "
        "Your responsibility is to verify final stock and delivery feasibility and record confirmed sales. "
        "CRITICAL ANTI-LOOP RULES: "
        "1. Only call `finalize_customer_sale` when ALL items in the customer's order are confirmed "
        "in stock (or restocked on time) and meet the delivery deadline. "
        "2. Call `finalize_customer_sale` ONCE per fulfilled line item. "
        "3. If any required item is unavailable or misses the deadline, do NOT record partial sales; "
        "clearly explain why the order cannot be finalized."
    ),
)


@sales_agent.tool_plain
def finalize_customer_sale(
    item_description: str,
    quantity: int,
    final_price: float,
    request_date: str,
    customer_deadline: str,
) -> str:
    """
    Verify stock availability and delivery feasibility, then record a 'sales' transaction.
    """
    catalog_name = resolve_catalog_item(item_description)
    if not catalog_name:
        return f"SALE_REJECTED: '{item_description}' is not carried in our catalog."

    df = get_stock_level(catalog_name, request_date)
    current_stock = int(df["current_stock"].iloc[0]) if not df.empty else 0

    if current_stock < quantity:
        eta = get_supplier_delivery_date(request_date, quantity - current_stock)
        if customer_deadline and eta > customer_deadline:
            return (
                f"SALE_REJECTED: Insufficient stock for {catalog_name} ({current_stock} available vs "
                f"{quantity} requested) and supplier restock ETA ({eta}) misses deadline ({customer_deadline})."
            )
        return (
            f"SALE_REJECTED: Insufficient stock for {catalog_name} ({current_stock} available vs {quantity} requested)."
        )

    tx_id = create_transaction(
        item_name=catalog_name,
        transaction_type="sales",
        quantity=quantity,
        price=round(final_price, 2),
        date=request_date,
    )
    return (
        f"SALE_CONFIRMED: Recorded sale of {quantity} units of '{catalog_name}' "
        f"for ${final_price:.2f} (Transaction #{tx_id})."
    )


# ==============================================================================
# AGENT 1: ORCHESTRATOR AGENT (CUSTOMER-FACING MANAGER)
# ==============================================================================

orchestrator_agent = Agent(
    llm_model,
    name="orchestrator_agent",
    instructions=(
        "You are the Lead Customer Operations Orchestrator at Munder Difflin Paper Company. "
        "For every incoming customer inquiry:"
        "1. Extract the requested items, quantities (convert reams to sheets where 1 ream = 500 sheets "
        "ONLY if explicitly needed, or keep unit counts consistent with catalog pricing), request date, "
        "and customer delivery deadline."
        "2. Optionally call `check_company_health` once for internal asset awareness."
        "3. Delegate to `consult_inventory_agent` ONCE with all requested items, quantities, request date, "
        "and delivery deadline to verify catalog availability, stock levels, and restock feasibility."
        "4. Delegate to `consult_quoting_agent` ONCE for all valid catalog items to generate an itemized "
        "bulk-discounted quote."
        "5. If ALL requested items are available/restocked on time by the customer's deadline, delegate to "
        "`consult_sales_agent` ONCE to finalize the sales transactions using the discounted line-item prices."
        "6. If ANY requested item is not in our catalog, out of stock past the deadline, or cannot be procured, "
        "do NOT finalize the order—politely decline the unfulfillable order and provide a clear, transparent "
        "explanation of which items failed and why, while sharing the quote for available items."
        "SECURITY & PRIVACY RULE: Never expose internal company cash balances, profit margins, wholesale costs, "
        "or internal database/system error messages in your response to the customer."
    ),
)


@orchestrator_agent.tool_plain
def check_company_health(as_of_date: str) -> str:
    """Run an internal financial and inventory health report as of `as_of_date` (YYYY-MM-DD)."""
    report = generate_financial_report(as_of_date)
    return (
        f"INTERNAL HEALTH REPORT ({report['as_of_date']}): "
        f"Cash=${report['cash_balance']:.2f}, "
        f"InventoryValue=${report['inventory_value']:.2f}, "
        f"TotalAssets=${report['total_assets']:.2f}"
    )


@orchestrator_agent.tool
async def consult_inventory_agent(ctx: RunContext[None], task_prompt: str) -> str:
    """Delegate inventory checks, supplier timeline lookups, and restock orders to Inventory Agent."""
    res = await inventory_agent.run(task_prompt, usage=ctx.usage)
    return res.output


@orchestrator_agent.tool
async def consult_quoting_agent(ctx: RunContext[None], task_prompt: str) -> str:
    """Delegate historical quote lookups and bulk-discounted quote calculations to Quoting Agent."""
    res = await quoting_agent.run(task_prompt, usage=ctx.usage)
    return res.output


@orchestrator_agent.tool
async def consult_sales_agent(ctx: RunContext[None], task_prompt: str) -> str:
    """Delegate final stock/deadline validation and customer sale recording to Sales Agent."""
    res = await sales_agent.run(task_prompt, usage=ctx.usage)
    return res.output

def sanitize_customer_response(response: str) -> str:
    """Remove internal IDs and operational markers from customer-facing text."""
    if not response:
        return response

    sanitized = re.sub(r'\s*\(Transaction #\d+\)', '', response)
    sanitized = re.sub(r'Transaction #\d+', 'confirmation record', sanitized)
    sanitized = re.sub(r'\bTX[-_]?\d+\b', 'confirmation record', sanitized, flags=re.IGNORECASE)
    return sanitized.strip()

def call_multi_agent_system(request_with_date: str) -> str:
    """Execute the multi-agent workflow with unrestricted request_limit to prevent UsageLimitExceeded."""
    result = orchestrator_agent.run_sync(
        request_with_date,
        usage_limits=UsageLimits(request_limit=None),
    )
    return sanitize_customer_response(result.output)


# ==============================================================================
# TEST RUNNER
# ==============================================================================

def run_test_scenarios():
    print("Initializing Database...")
    init_database(db_engine)
    try:
        quote_requests_sample = pd.read_csv("quote_requests_sample.csv")
        quote_requests_sample["request_date"] = pd.to_datetime(
            quote_requests_sample["request_date"], format="%m/%d/%y", errors="coerce"
        )
        quote_requests_sample.dropna(subset=["request_date"], inplace=True)
        quote_requests_sample = quote_requests_sample.sort_values("request_date")
    except Exception as e:
        print(f"FATAL: Error loading test data: {e}")
        return

    # Get initial state
    initial_date = quote_requests_sample["request_date"].min().strftime("%Y-%m-%d")
    report = generate_financial_report(initial_date)
    current_cash = report["cash_balance"]
    current_inventory = report["inventory_value"]

    results = []
    for idx, row in quote_requests_sample.iterrows():
        request_date = row["request_date"].strftime("%Y-%m-%d")

        print(f"\n=== Request {idx+1} ===")
        print(f"Context: {row['job']} organizing {row['event']}")
        print(f"Request Date: {request_date}")
        print(f"Cash Balance: ${current_cash:.2f}")
        print(f"Inventory Value: ${current_inventory:.2f}")

        # Process request
        request_with_date = f"{row['request']} (Date of request: {request_date})"
        response = call_multi_agent_system(request_with_date)

        # Update state
        report = generate_financial_report(request_date)
        current_cash = report["cash_balance"]
        current_inventory = report["inventory_value"]

        print(f"Response: {response}")
        print(f"Updated Cash: ${current_cash:.2f}")
        print(f"Updated Inventory: ${current_inventory:.2f}")

        results.append(
            {
                "request_id": idx + 1,
                "request_date": request_date,
                "cash_balance": current_cash,
                "inventory_value": current_inventory,
                "response": response,
            }
        )

        time.sleep(1)

    # Final report
    final_date = quote_requests_sample["request_date"].max().strftime("%Y-%m-%d")
    final_report = generate_financial_report(final_date)
    print("\n===== FINAL FINANCIAL REPORT =====")
    print(f"Final Cash: ${final_report['cash_balance']:.2f}")
    print(f"Final Inventory: ${final_report['inventory_value']:.2f}")

    # Save results
    pd.DataFrame(results).to_csv("test_results.csv", index=False)
    return results


if __name__ == "__main__":
    results = run_test_scenarios()