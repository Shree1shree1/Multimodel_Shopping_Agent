# 🛒 AI Shopping Assistant

An AI-powered shopping assistant built with **LangChain**, **Groq**, and **Streamlit**. Describe what you want to buy (or upload a photo of a product), and the agent will search the store, pull in customer ratings, and place an order for you — all through natural conversation.

---

## ✨ Features

- **Conversational shopping** — describe what you're looking for in plain English (e.g. *"I want organic honey under $15 with 4+ rating"*) and the agent finds matching products.
- **Shop by image** — upload a photo of a product and the assistant analyzes it (via a vision-capable LLM) and searches the store for similar items.
- **Rating-aware recommendations** — every candidate product is checked against its average customer rating before being presented.
- **Conversational checkout** — confirm an order with a simple "yes" or by referencing the product number; the agent places the order and returns a confirmation.
- **Persistent local store** — products, reviews, and orders are all stored in a local SQLite database.

---

## 🏗️ Architecture

```
├── app.py                 # Streamlit chat UI (frontend)
├── shopping_agent.py       # LangChain agent, tools, and system prompt
├── database_setup.py       # Creates & seeds store.db (products + reviews)
├── reviews_api.py          # Helper functions for aggregating product ratings
└── store.db                # SQLite database (generated)
```

**Flow:**
1. `app.py` renders the Streamlit chat interface and manages conversation state (`st.session_state.messages`).
2. User input (text or uploaded image) is passed to the LangChain agent defined in `shopping_agent.py`.
3. The agent (powered by a Groq-hosted LLM) decides which tool to call:
   - `search_products` — query the product catalog by keyword, price, and organic status
   - `get_rating` — fetch average rating and review count for a product
   - `checkout` — place an order for a given product ID
   - `describe_and_search_product_image` — analyze an uploaded image and run a product search based on what it detects
4. The agent's final response is rendered back in the chat.

---

## 🛠️ Tech Stack

- [Streamlit](https://streamlit.io/) — chat-based web UI
- [LangChain](https://python.langchain.com/) (`create_agent`, `@tool`) — agent orchestration and tool calling
- [Groq](https://groq.com/) (via `langchain-groq`) — fast LLM inference for both chat and vision
- [SQLite](https://www.sqlite.org/) — lightweight local database for products, reviews, and orders
- Python 3.10+

---

## 📦 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/<your-username>/<your-repo>.git
   cd <your-repo>
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

   If you don't have a `requirements.txt` yet, create one with:
   ```
   streamlit
   langchain
   langchain-core
   langchain-groq
   python-dotenv
   ```

4. **Set up environment variables**

   Create a `.env` file in the project root:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   ```

5. **Initialize the database**
   ```bash
   python database_setup.py
   ```
   This creates `store.db` and seeds it with sample products and reviews.

---

## 🚀 Usage

Start the Streamlit app:

```bash
streamlit run app.py
```

Then, in the app:

- **Text search** — type a request in the chat box, e.g.:
  > "I want organic honey under $15 with 4+ rating"
- **Image search** — use the sidebar to upload a product photo and click **Find similar products**.
- **Checkout** — once the assistant shows a list of matching products, confirm with "yes," "order number 2," or similar phrasing to place an order.

---

## 🗄️ Database Schema

| Table      | Description                                              |
|------------|------------------------------------------------------------|
| `products` | Product catalog — id, name, category, price, description, is_organic |
| `reviews`  | Customer reviews — product_id, rating, reviewer_name, review_text |
| `orders`   | Placed orders — product_id, product_name, price, ordered_at |

---

## 🔧 Configuration Notes

- The agent model and vision model are both configured in `shopping_agent.py`:
  ```python
  llm = ChatGroq(model="<model-name>", temperature=0)
  vision_llm = ChatGroq(model="<model-name>", temperature=0)
  ```
  Update these to match the models available in your Groq account.
- All product filtering (price, organic status) happens inside `search_products` in `shopping_agent.py` — adjust the SQL logic there if you extend the schema.

---

## 🧭 Roadmap Ideas

- [ ] Add user authentication and per-user order history
- [ ] Support multi-item orders / cart functionality
- [ ] Add pagination for large result sets
- [ ] Deploy to Streamlit Community Cloud

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).