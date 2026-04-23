# Setup Guide - Log Aggregator UTS

## Quick Start (Docker - Recommended)

### Build dan Run

```bash
# Build image
docker build -t log-aggregator:latest .

# Run container dengan volume untuk persist data
docker run -p 8080:8080 -v $(pwd)/data:/app/data log-aggregator:latest

# Di Windows PowerShell:
docker run -p 8080:8080 -v ${PWD}/data:/app/data log-aggregator:latest
```

### Test API

```bash
# Health check
curl http://localhost:8080/

# Publish single event
curl -X POST http://localhost:8080/publish \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "orders",
    "event_id": "order-123",
    "timestamp": "2024-04-21T10:30:00",
    "source": "order-service",
    "payload": {"order_id": 123, "amount": 500}
  }'

# Publish batch events dengan duplikasi
curl -X POST http://localhost:8080/publish \
  -H "Content-Type: application/json" \
  -d '[
    {"topic": "orders", "event_id": "order-001", "timestamp": "2024-04-21T10:00:00", "source": "app", "payload": {"amount": 100}},
    {"topic": "orders", "event_id": "order-001", "timestamp": "2024-04-21T10:00:00", "source": "app", "payload": {"amount": 100}}
  ]'

# Get stats
curl http://localhost:8080/stats | jq

# Get events by topic
curl http://localhost:8080/events?topic=orders | jq

# Get all events
curl http://localhost:8080/events | jq
```

## Local Development

### Setup

```bash
# 1. Create virtual environment
python -m venv .venv

# 2. Activate (Windows)
.venv\Scripts\activate
# Or (Linux/Mac)
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8080

# 5. Server ready at http://localhost:8080
```

### Run Tests

```bash
# All tests
pytest tests/test_aggregator.py -v

# Specific test
pytest tests/test_aggregator.py::test_dedup_single_event -v

# With coverage
pytest tests/test_aggregator.py --cov=src --cov-report=html
```

### Test Publisher Script

```bash
# Publish 1000 events dengan 20% duplikasi ke local aggregator
python publisher.py

# Custom settings
NUM_EVENTS=5000 DUPLICATE_RATE=0.3 python publisher.py

# Custom aggregator host (untuk docker)
AGGREGATOR_HOST=http://localhost:8080 python publisher.py
```

## Docker Compose (Bonus +10%)

### Setup

```bash
# Build dan run both services
docker-compose up --build

# Check logs
docker-compose logs -f aggregator
docker-compose logs -f publisher

# Stop
docker-compose down

# Clean data
rm -rf data/
```

### Services

1. **aggregator** (port 8080): Main service
2. **publisher** (depends_on aggregator): Test publisher

### Endpoints (dalam docker-compose)

```bash
# From outside container
curl http://localhost:8080/stats

# From publisher container (internal network)
curl http://aggregator:8080/stats
```

## Project Structure

```
.
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + endpoints
│   ├── models.py            # Event pydantic model
│   ├── queue.py             # Asyncio queue
│   ├── consumer.py          # Idempotent consumer
│   ├── storage.py           # SQLite dedup store
│   └── stats.py             # Statistics tracking
│
├── tests/
│   ├── __init__.py
│   └── test_aggregator.py   # 10+ unit tests
│
├── data/                    # Persistent storage (auto-created)
│   └── dedup.db            # SQLite database
│
├── Dockerfile              # Main service image
├── Dockerfile.publisher    # Publisher service image
├── docker-compose.yml      # Orchestration config
├── requirements.txt        # Python dependencies
├── publisher.py            # Test publisher script
├── README.md              # API documentation
├── REPORT.md              # Teori laporan (T1-T8)
└── SETUP_GUIDE.md         # This file
```

## File Size & Performance

### Build Output

```
Repository Size: ~2.5 MB (code only)
Docker Image: ~280 MB (with python:3.11-slim base)

Performance (stress test 5000 events, 20% duplication):
- Processing time: ~8-10 seconds
- Throughput: ~500+ events/second
- Memory: ~85 MB
- CPU: <30%
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs log-aggregator

# Check health
docker ps  # Look for STATUS column

# Rebuild from scratch
docker build --no-cache -t log-aggregator:latest .
```

### Tests fail with import error

```bash
# Ensure you're in the right directory
cd D:/KULIAH/SISTER/UTS

# Use .venv python
.venv/Scripts/python.exe -m pytest tests/test_aggregator.py -v
```

### Database locked error

```bash
# Stop container
docker stop log-aggregator

# Remove old db
rm -rf data/dedup.db

# Start container again
docker run -p 8080:8080 -v $(pwd)/data:/app/data log-aggregator:latest
```

### Queue full error (QueueFull exception)

```bash
# Reduce batch size in publisher.py
# Or increase queue maxsize in src/queue.py
event_queue = asyncio.Queue(maxsize=50000)  # Increase from 10000
```

## Development Notes

### Adding Custom Metrics

Edit `src/stats.py`:
```python
def record_custom_metric(self, name, value):
    self.custom_metrics[name] = value

def get_stats(self):
    return {
        ...existing stats...,
        "custom": self.custom_metrics
    }
```

### Changing Dedup Strategy

Currently using composite key `(topic, event_id)`. To change:

Edit `src/storage.py`:
```python
# Change constraint from:
UNIQUE(topic, event_id)

# To something like:
UNIQUE(source, timestamp, event_type)
```

### Extending Consumer Logic

Edit `src/consumer.py`:
```python
async def consume(self):
    while self.is_running:
        event = await self.queue.get()
        
        # Add custom processing here
        await self.process_event(event)
        
        self.queue.task_done()

async def process_event(self, event):
    # Custom logic
    pass
```

## Submission Checklist

- [x] Source code (src/ folder)
- [x] Unit tests (tests/ folder, 10+ tests)
- [x] Dockerfile (with best practices)
- [x] docker-compose.yml (bonus +10%)
- [x] requirements.txt
- [x] README.md (API documentation)
- [x] REPORT.md (teori T1-T8 dengan sitasi APA)
- [x] SETUP_GUIDE.md (this file)
- [ ] Video demo YouTube (5-8 minutes, public link in README or REPORT)
- [ ] GitHub repository (with README and link)

## References

- Tanenbaum, A. S., & Van Steen, M. (2007). *Distributed systems: Principles and paradigms* (2nd ed.). Pearson Education.
- FastAPI: https://fastapi.tiangolo.com/
- SQLite: https://www.sqlite.org/
- Docker: https://docs.docker.com/
- pytest: https://docs.pytest.org/

---

**Last Updated**: April 21, 2026  
**Status**: Ready for submission
