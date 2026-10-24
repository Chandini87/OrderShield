# OrderShield

[![tests](https://github.com/<Chandini87>/ordershield/actions/workflows/tests.yml/badge.svg)](https://github.com/<Chandini87>/ordershield/actions)

A reliable e-commerce order processing backend built with Python and FastAPI. It simulates how an online store takes orders, reserves inventory, processes payments and recovers from failures.

## The problems it solves

Simple ordering systems break in predictable ways. OrderShield is designed around them:

| Problem | How OrderShield handles it |
|---|---|
| A customer double-clicks and creates two orders | `Idempotency-Key` header plus a database unique constraint |
| Two customers buy the last item at the same time | Atomic conditional stock update (`UPDATE ... WHERE stock >= qty`) |
| Payment fails after stock was reserved | Stock is released in the same transaction that marks the order `PAYMENT_FAILED` |
| An order jumps to an impossible state | Explicit status transition rules |
| Something goes wrong and nobody can tell why | Structured JSON logs with a request ID on every line |

## Tech stack

Python 3.12, FastAPI, SQLAlchemy 2.0, SQLite, Pydantic, pytest, GitHub Actions

## Features

- Product management and stock tracking
- Order placement with simulated payments
- Idempotent order creation (safe retries)
- Concurrency-safe stock reservation
- Order cancellation with stock release
- Enforced order status transitions
- Consistent error responses with machine-readable codes
- Structured JSON logging with request IDs
- Automated tests, including a multi-threaded race test
- Interactive API docs at `/docs`

## Project structure

```
ordershield/
├── .github/workflows/tests.yml   # runs the test suite on every push
├── app/
│   ├── main.py                   # app setup, error handler, request logging
│   ├── database.py               # engine and session
│   ├── models.py                 # Product and Order tables
│   ├── schemas.py                # request/response validation
│   ├── exceptions.py             # business errors with codes
│   ├── logging_config.py         # JSON logging and request IDs
│   ├── routers/
│   │   ├── products.py
│   │   └── orders.py
│   └── services/
│       ├── order_service.py      # reservation, payment, cancellation logic
│       ├── payment_service.py    # simulated payment gateway
│       └── transitions.py        # allowed status changes
├── tests/
│   ├── conftest.py
│   ├── test_products.py
│   ├── test_orders.py
│   ├── test_transitions.py
│   └── test_concurrency.py
├── pytest.ini
└── requirements.txt
```

Routers only handle HTTP. All business rules live in `services/`.

## Getting started

```bash
git clone https://github.com/<your-username>/ordershield.git
cd ordershield

python -m venv venv
# Windows (PowerShell)
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API runs at http://127.0.0.1:8000 and the interactive docs are at http://127.0.0.1:8000/docs.

Run the tests:

```bash
pytest
```

### Configuration

| Variable | Default | Meaning |
|---|---|---|
| `PAYMENT_FAILURE_RATE` | `0.2` | Chance (0 to 1) that a simulated payment fails. Use `0` for always succeed, `1` for always fail. |

## API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/products` | Add a product |
| GET | `/products` | List products |
| GET | `/products/{id}` | Get one product |
| POST | `/orders` | Place an order (requires `Idempotency-Key` header) |
| GET | `/orders/{id}` | Get order status |
| POST | `/orders/{id}/cancel` | Cancel an order and release its stock |

### Example

```bash
# add a product
curl -X POST http://127.0.0.1:8000/products \
  -H "Content-Type: application/json" \
  -d '{"name": "Mobile Phone", "price": 15000, "stock": 1}'

# place an order
curl -X POST http://127.0.0.1:8000/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-001" \
  -d '{"product_id": 1, "quantity": 1}'
```

Response (`201`):

```json
{
  "id": 1,
  "product_id": 1,
  "quantity": 1,
  "total_price": 15000.0,
  "status": "CONFIRMED",
  "created_at": "2026-10-24T09:12:01.123456"
}
```

Sending the same request again with the same key returns `200` and the original order. No second order is created and the customer is not charged twice.

### Error responses

Business errors return `detail` (human-readable) and `code` (for programs):

```json
{ "detail": "Insufficient stock. Available: 0", "code": "INSUFFICIENT_STOCK" }
```

| HTTP | Code | When |
|---|---|---|
| 400 | `INSUFFICIENT_STOCK` | Not enough units available |
| 404 | `PRODUCT_NOT_FOUND` / `ORDER_NOT_FOUND` | Unknown id |
| 409 | `INVALID_TRANSITION` | Status change not allowed (e.g. cancelling twice) |
| 422 | `IDEMPOTENCY_CONFLICT` | Same key reused with a different request |
| 422 | (validation) | Malformed input, e.g. quantity 0 or missing header |

## Order lifecycle

```
PENDING ──► STOCK_RESERVED ──► CONFIRMED ──► CANCELLED
   │              │
   │              ├──► PAYMENT_FAILED   (final, stock released)
   │              └──► CANCELLED        (final, stock released)
   └──► CANCELLED
```

`PAYMENT_FAILED` and `CANCELLED` are final states.

## Design decisions

- **Atomic stock reservation.** Checking stock in Python and then updating it leaves a gap where two requests can both pass the check. Instead, the check and the decrement happen in one SQL statement, and the affected row count tells the code whether it succeeded.
- **Idempotency enforced by the database.** The service checks for an existing key first, and a unique constraint catches two identical requests that arrive at the same instant.
- **All-or-nothing changes.** The order row and the stock change are committed together. A payment failure marks the order and releases stock in one commit.
- **Same pattern for cancellation.** Cancel only succeeds if the status is still what was read, so two simultaneous cancels cannot release stock twice.
- **Thin routers, testable services.** Payment is injected as a dependency, so tests use a fake gateway.

## Logging

Every log line is JSON and carries the request ID, which is also returned in the `X-Request-ID` response header:

```json
{"timestamp": "2026-10-24T09:12:01.123456+00:00", "level": "INFO", "logger": "ordershield.orders", "event": "stock_reserved", "request_id": "3f2a9c1e-...", "order_id": 1, "product_id": 1, "quantity": 1}
```

Events include `stock_reserved`, `insufficient_stock`, `duplicate_request_ignored`, `order_confirmed`, `payment_failed`, `stock_released` and `order_cancelled`.

## Testing

20 tests cover:

- Input validation and unknown products
- Insufficient stock leaving no partial data
- Duplicate requests (stock reduced once, customer charged once)
- Same key with a different payload
- Payment failure releasing stock
- Cancellation, including double cancel
- Status transition rules
- 10 threads racing for the last item, and 10 threads sending the same idempotency key

## Known limitations and future work

- If the server crashes after stock is reserved but before payment finishes, the order stays in `STOCK_RESERVED`. A background job to retry or expire such orders would fix this (Redis and Celery are the planned approach).
- SQLite is used for simplicity. PostgreSQL support, Alembic migrations and Docker are planned.
- Payment is simulated, with no real gateway.
- No authentication or multi-item orders yet.

## Author

Chandini, B.Tech in Computer Science and Engineering