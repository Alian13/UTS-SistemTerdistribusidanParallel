# Log Aggregator - Pub-Sub dengan Idempotent Consumer

Sistem log aggregator berbasis Python dengan architecture Pub-Sub yang menerapkan idempotency dan deduplication untuk menjamin konsistensi event processing.

## Fitur Utama

- **Publish-Subscribe Pattern**: Asynchronous event publishing dengan internal queue
- **Idempotent Consumer**: Event dengan (topic, event_id) yang sama hanya diproses sekali
- **Persistent Deduplication**: SQLite-based dedup store yang tahan terhadap restart container
- **At-Least-Once Delivery Semantics**: Simulasi duplikasi dengan consumer idempotency
- **Real-time Statistics**: Tracking received, processed, duplicates, dan per-topic metrics
- **FastAPI REST API**: Clean API untuk publish, query events, dan statistics

## Arsitektur

```
┌─────────────────────────────────────────────────┐
│         Publisher (HTTP Client)                  │
│         POST /publish (batch events)             │
└────────────┬────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│              FastAPI Application                │
├─────────────────────────────────────────────────┤
│  • Event Validation (Pydantic)                  │
│  • Async Queue (asyncio.Queue)                  │
│  • Statistics Tracking                          │
└────────┬─────────────────────────────┬──────────┘
         │                             │
         ▼                             ▼
    Async Queue              GET /events, /stats
         │
         ▼
┌──────────────────────────┐
│  Idempotent Consumer     │
│  (Async Processing)      │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  Dedup Store (SQLite)    │
│  • is_duplicate() check  │
│  • store_event()         │
│  • Persistent storage    │
└──────────────────────────┘
```

## Endpoints

### 1. Health Check
```
GET /
Response: {"status": "ok", "service": "Log Aggregator", "version": "1.0.0"}
```

### 2. Publish Events
```
POST /publish
Content-Type: application/json

Request Body (single event):
{
  "topic": "orders",
  "event_id": "order-123",
  "timestamp": "2024-04-21T10:30:00",
  "source": "order-service",
  "payload": {"order_id": "123", "amount": 500}
}

Request Body (batch events):
[{...}, {...}]

Response:
{
  "status": "accepted",
  "count": 10,
  "queue_size": 45
}
```

### 3. Get Processed Events
```
GET /events?topic=orders

Response:
{
  "topic": "orders",
  "count": 150,
  "events": [
    {
      "topic": "orders",
      "event_id": "order-123",
      "timestamp": "2024-04-21T10:30:00",
      "source": "order-service",
      "payload": {...},
      "processed_at": "2024-04-21T10:30:01.234567"
    }
  ]
}

GET /events (all events):
Response:
{
  "total_events": 5000,
  "topics": ["orders", "payments", "users"],
  "events": [...]
}
```

### 4. Get Statistics
```
GET /stats

Response:
{
  "received": 5000,
  "unique_processed": 4000,
  "duplicate_dropped": 1000,
  "topics": {"orders": 2000, "payments": 1500, "users": 500},
  "uptime_seconds": 125.45,
  "timestamp": "2024-04-21T10:35:00",
  "store": {
    "total_events_stored": 4000,
    "unique_topics": 3
  },
  "queue_size": 0
}
```

## Build & Run

### Docker (Recommended)

```bash
# Build image
docker build -t log-aggregator:latest .

# Run container
docker run -p 8080:8080 -v $(pwd)/data:/app/data log-aggregator:latest

# Check health
curl http://localhost:8080/

# Publish events
curl -X POST http://localhost:8080/publish \
  -H "Content-Type: application/json" \
  -d '[
    {"topic": "orders", "event_id": "evt-1", "timestamp": "2024-04-21T10:30:00", "source": "app", "payload": {"order": 1}},
    {"topic": "orders", "event_id": "evt-1", "timestamp": "2024-04-21T10:30:00", "source": "app", "payload": {"order": 1}}
  ]'

# Check stats
curl http://localhost:8080/stats
```

### Docker Compose (Bonus)

```bash
# Build dan run both aggregator dan test publisher
docker-compose up --build

# Check logs
docker-compose logs -f aggregator
docker-compose logs -f publisher

# Stop
docker-compose down
```

### Local Development

```bash
# Setup virtual environment
python -m venv .venv
source .venv/Scripts/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8080

# Run tests
pytest tests/test_aggregator.py -v

# Run publisher for testing
python publisher.py
```

## Unit Tests

```bash
# Run all tests (7 test cases)
pytest tests/test_aggregator.py -v

# Run specific test
pytest tests/test_aggregator.py::test_dedup_single_event -v

# Run with coverage
pytest tests/test_aggregator.py --cov=src --cov-report=html
```

### Test Cases Coverage

1. **test_dedup_single_event**: Validasi dedup - event dikirim 1x, diproses 1x
2. **test_dedup_multiple_duplicates**: Event dikirim 3x, hanya 1x diproses (2x di-reject)
3. **test_dedup_store_persistence**: Setelah restart (new DB instance), dedup tetap efektif
4. **test_event_schema_validation**: Schema validation untuk Event model
5. **test_event_schema_timestamp_iso8601**: Timestamp harus ISO8601 format
6. **test_stats_consistency**: GET /stats valid (received = unique_processed + duplicate_dropped)
7. **test_stats_topics_counter**: Per-topic counter accurate
8. **test_get_events_by_topic**: GET /events by topic konsisten
9. **test_stress_large_batch**: Stress test 5000+ events dengan 20% duplikasi
10. **test_consumer_idempotency**: Consumer idempotency verification

## Desain Keputusan

### 1. Deduplication Strategy

**Key**: Composite unique key `(topic, event_id)`
- Event dengan topic+event_id yang sama = duplikat
- Disimpan di SQLite dengan UNIQUE constraint
- Deterministik dan reproducible

**Benefit**:
- Konsisten across restart
- Atomic pada database level
- Mudah di-query

### 2. Idempotent Consumer

**Strategy**: Check sebelum insert
```python
if not is_duplicate(topic, event_id):
    store_event(...)
    record_processed()
else:
    record_duplicate()
```

**At-Least-Once Delivery**:
- Publisher bisa mengirim event berkali-kali
- Consumer guarantee: process hanya 1x
- Retry-safe: event yang gagal bisa dikirim ulang

### 3. Persistent Dedup Store

**Technology**: SQLite embedded database
```sql
CREATE TABLE processed_events (
    topic TEXT NOT NULL,
    event_id TEXT NOT NULL,
    UNIQUE(topic, event_id)
)
```

**Advantages**:
- No external dependencies
- ACID compliance
- Tahan crash/restart
- Performa O(1) lookup

### 4. Ordering & Consistency

**Temporal Ordering**:
- Event timestamp: publisher-provided (ISO8601)
- processed_at: server-provided (ordering di consumer)
- Per-topic ordering: via `processed_at` DESC

**Eventual Consistency**:
- In-process: consumer memproses queue sequentially
- At-rest: dedup store guarantees no duplicate at rest state
- Consumer start → queue process → dedup store write (all atomic)

### 5. Queue-Based Architecture

**In-Memory Queue**: `asyncio.Queue(maxsize=10000)`
- Decouples publisher dari consumer
- Publisher: O(1) put (non-blocking)
- Consumer: async processing di background

**Rationale**:
- Scalable: async I/O tidak block
- Fail-safe: queue lost on restart (OK, dupdup store persists)
- Simple: no external message broker needed

## Performance Metrics

Tested pada:
- 5000 events dengan 20% duplikasi (1000 unique, 4000 duplicate)
- Throughput: ~500+ events/sec
- Memory: < 100MB
- Processing time: < 10 seconds

## Failure Modes & Mitigations

| Failure | Impact | Mitigation |
|---------|--------|-----------|
| **Duplicate Event** | Consumer process 2x | Dedup store check before insert |
| **Container Crash** | Queue lost, events may be reprocessed | Dedup store persists on restart |
| **Out-of-Order Events** | Topics may have mixed orders | Per-topic ordering via timestamp |
| **Full Queue** | New events rejected | Batch publishing + monitoring |
| **DB Corruption** | Cannot guarantee dedup | SQLITE ACID + transaction |

## Technologies

- **Framework**: FastAPI 0.104.1
- **Async Runtime**: asyncio
- **Validation**: Pydantic 2.5.0
- **Database**: SQLite3 (embedded)
- **Testing**: pytest 7.4.3
- **Server**: Uvicorn 0.24.0
- **Container**: Docker

## Struktur Project

```
.
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── models.py            # Event pydantic model
│   ├── queue.py             # Async queue
│   ├── consumer.py          # Idempotent consumer
│   ├── storage.py           # SQLite dedup store
│   └── stats.py             # Statistics tracker
├── tests/
│   ├── __init__.py
│   └── test_aggregator.py   # 10 unit tests
├── Dockerfile
├── Dockerfile.publisher     # For docker-compose bonus
├── docker-compose.yml       # Bonus: 2 services
├── requirements.txt
├── publisher.py             # Test publisher script
└── README.md
```

## References & Sitasi

Untuk laporan teori (T1-T8), referensi ke:
- Tanenbaum, A. S., & Van Steen, M. (2007). Distributed systems: Principles and paradigms (2nd ed.). Pearson Education. [Bab 1-7]

## Demo Video

Video demo tersedia di YouTube (link di laporan PDF/MD).

## Maintenance & Troubleshooting

### Database Grows Too Large
```bash
# Clear old events (dalam container)
python -c "from src.storage import dedup_store; dedup_store.clear()"
```

### Queue Full
- Reduce batch size di publisher
- Increase queue maxsize di queue.py
- Monitor /stats endpoint

### Performance Issues
- Check CPU/Memory usage: `docker stats`
- Check logs: `docker logs log-aggregator`
- Run tests untuk benchmark

## License

MIT
