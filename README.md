# OrderShield

A backend that simulates how an e-commerce platform processes orders, tracks inventory and handles failures, built with Python and FastAPI.

OrderShield is designed around problems that simple ordering systems get wrong: duplicate orders from double-clicks, overselling the last item when two customers buy at once, and orders left half-finished after a payment failure.

## Status

| Phase | Scope | Status |
|---|---|---|
| 1 | Products, orders, stock tracking, input validation, tests | Done |
| 2 | Idempotency keys, transactional stock updates, concurrency safety, simulated payments, stock release on failure | In progress |
| 3 | Concurrency and failure tests, structured logging, API docs | Planned |

## Tech Stack

- Python 3.12
- FastAPI (REST API)
- SQLAlchemy 2.0 (ORM)
- SQLite (PostgreSQL planned)
- Pydantic (request validation)
- pytest + httpx (testing)

## Project Structure

```
ordershield/
├── app/
│   ├── main.py          # FastAPI app and router registration
│   ├── database.py      # database engine and session
│   ├── models.py        # SQLAlchemy tables (Product, Order)
│   ├── schemas.py       # Pydantic request/response models
│   └── routers/
│       ├── products.py  # product endpoints
│       └── orders.py    # order endpoints
├── tests/
│   ├── conftest.py      # in-memory test database
│   ├── test_products.py
│   └── test_orders.py
├── pytest.ini
└── requirements.txt
```

## Getting Started

### 1. Clone and enter the project

```bash
git clone https://github.com/<Chandini87>/ordershield.git
cd ordershield
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# Windows (PowerShell)
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the server

```bash
uvicorn app.main:app --reload
```

The API runs at http://127.0.0.1:8000. Interactive documentation (Swagger UI) is at http://127.0.0.1:8000/docs.

### 5. Run the tests

```bash
pytest -v
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/products` | Add a product |
| GET | `/products` | List all products |
| GET | `/products/{id}` | Get one product |
| POST | `/orders` | Place an order |
| GET | `/orders/{id}` | Get order status |

### Example

Create a product:

```bash
curl -X POST http://127.0.0.1:8000/products \
  -H "Content-Type: application/json" \
  -d '{"name": "Mobile Phone", "price": 15000, "stock": 1}'
```

Place an order:

```bash
curl -X POST http://127.0.0.1:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"product_id": 1, "quantity": 1}'
```

Response:

```json
{
  "id": 1,
  "product_id": 1,
  "quantity": 1,
  "total_price": 15000.0,
  "status": "STOCK_RESERVED",
  "created_at": "2026-10-23T08:55:12.123456"
}
```

Ordering more than the available stock returns `400` with `Insufficient stock`. An unknown product returns `404`. Invalid input (such as quantity 0) returns `422`.

## Order Statuses

`PENDING`, `STOCK_RESERVED`, `PAYMENT_FAILED`, `CONFIRMED`, `CANCELLED`

Transition rules between statuses are enforced starting in Phase 2.

## Roadmap

- Idempotency keys to prevent duplicate orders
- Atomic stock reservation to prevent overselling under concurrent requests
- Simulated payment service with stock release on failure
- Enforced order status transitions
- Structured logging
- PostgreSQL support and Docker

## Author

Chandini, B.Tech in Computer Science and Engineering