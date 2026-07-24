import base64
import json
import os
import sqlite3
from typing import Optional, Union

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

from reviews_api import get_product_rating

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), "store.db")

llm = ChatGroq(model="qwen/qwen3.6-27b", temperature=0)
vision_llm = ChatGroq(model="qwen/qwen3.6-27b", temperature=0)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
def _normalize_organic(value) -> Optional[bool]:
    """
    Coerce whatever the model sends us into True / False / None.
    Handles real booleans, and the strings some models emit instead of a
    true null ("none", "null", "unknown", "unclear", ""), and "true"/"false" strings.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("", "none", "null", "unknown", "unclear", "any", "n/a"):
            return None
        if v in ("true", "yes", "organic", "1"):
            return True
        if v in ("false", "no", "non_organic", "non-organic", "0"):
            return False
    return None
@tool
def search_products(
    query: str,
    max_price: Optional[float] = None,
    is_organic: Optional[Union[bool, str]] = None,
) -> str:
    """
    Search the product database by keyword (matched against name, description, and category).
    Optionally filter by maximum price and/or organic status.

    is_organic: pass true to filter to organic products, false to filter to
    non-organic products, or omit this parameter entirely if organic status doesn't matter.

    Returns a JSON array of matching products, each with: id, name, category, price,
    description, is_organic.
    """
    is_organic_bool = _normalize_organic(is_organic)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    sql = "SELECT id, name, category, price, description, is_organic FROM products WHERE 1=1"
    params: list = []

    if query:
        sql += " AND (name LIKE ? OR description LIKE ? OR category LIKE ?)"
        like = f"%{query}%"
        params.extend([like, like, like])

    if max_price is not None:
        sql += " AND price <= ?"
        params.append(max_price)

    if is_organic_bool is not None:
        sql += " AND is_organic = ?"
        params.append(1 if is_organic_bool else 0)

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    products = [
        {
            "id":          row[0],
            "name":        row[1],
            "category":    row[2],
            "price":       row[3],
            "description": row[4],
            "is_organic":  bool(row[5]),
        }
        for row in rows
    ]
    return json.dumps(products)


@tool
def get_rating(product_id: int) -> str:
    """
    Get the average customer rating and total review count for a product by its ID.
    Returns a JSON object with: product_id, average_rating, review_count.
    """
    result = get_product_rating(product_id)
    return json.dumps(result)


@tool
def checkout(product_id: int) -> str:
    """
    Place an order for the given product ID. Saves the order to the database and returns
    a confirmation message with the order ID, product name, and price.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, price FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return f"Error: product with ID {product_id} not found."

    name, price = row
    cursor.execute(
        "INSERT INTO orders (product_id, product_name, price) VALUES (?, ?, ?)",
        (product_id, name, price),
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return (
        f"Order #{order_id} confirmed! '{name}' has been successfully ordered for ${price:.2f}. "
        f"Your order will arrive in 3-5 business days. Thank you for shopping with us!"
    )


@tool
def describe_and_search_product_image(image_path: str, max_price: Optional[float] = None) -> str:
    """Analyze a product image and search the store for matching products in one step."""
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()
    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"

    message = HumanMessage(content=[
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_data}"}},
        {"type": "text", "text": (
            "Look at this product image and extract its key attributes. "
            "Return ONLY valid JSON, no markdown fences, with these fields:\n"
            "- product_type\n- search_query\n- is_organic (true, false, or null)\n- description"
        )},
    ])

    raw = vision_llm.invoke([message]).content.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        attrs = json.loads(raw)
    except json.JSONDecodeError:
        return json.dumps({"error": "Could not parse image attributes", "raw": raw})

    is_organic = attrs.get("is_organic")
    if not isinstance(is_organic, bool):
        is_organic = None  # guard against "unclear", "null" strings, etc.

    return search_products.func(
        query=attrs.get("search_query", attrs.get("product_type", "")),
        max_price=max_price,
        is_organic=is_organic,
    )


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = create_agent(
    tools=[search_products, get_rating, checkout, describe_and_search_product_image],
    model=llm,
    system_prompt=(
        "You are a helpful shopping assistant. Follow these rules strictly.\n\n"
        "IMAGE SEARCH — when the user provides an image path:\n"
        "1. Call describe_product_image with the path to identify the product.\n"
        "2. Use the returned search_query and is_organic to call search_products.\n"
        "3. Continue with the BROWSING flow from step 2 onwards.\n\n"
        "BROWSING — when the user describes what they want to buy:\n"
        "1. Call search_products to find matching items (apply any price/organic filters given).\n"
        "2. For each candidate, call get_rating to retrieve its average rating.\n"
        "3. Filter by the user's minimum rating if specified.\n"
        "4. Present qualifying products as a numbered list. For each item use this exact format "
        "   (plain text, no backticks, no code blocks, no bold, no italic):\n\n"
        "   #<number>. <name> (ID:<product_id>) — $<price> ★<rating> — <organic or non-organic>\n\n"
        "   Add a blank line between each product entry for readability. "
        "   Always include (ID:X) so you can reference it later.\n"
        "5. If only one product qualifies, still show it in the list and ask: "
        "   'Would you like to order it? Just say yes or give me the number.'\n"
        "6. Do NOT call checkout at this stage.\n\n"
        "ORDERING — when the user confirms they want to buy (e.g. 'yes', 'sure', 'go ahead', "
        "'order number 2', 'the first one', 'get me #3'):\n"
        "1. Look at your previous message to find the (ID:X) for the chosen product "
        "   (if only one was listed and the user says 'yes', use that product's ID).\n"
        "2. Call checkout with that product_id (the number from (ID:X)).\n"
        "3. Confirm the order to the user in plain text.\n\n"
        "Never place an order unless the user explicitly confirms. "
        "Never guess a product_id — always take it from the (ID:X) in your own previous message."
    ),
)

if __name__ == "__main__":
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "I want to buy organic honey with 4.5+ rating and less than $20 price."
                    ),
                }
            ]
        }
    )
    print(result["messages"][-1].content)
