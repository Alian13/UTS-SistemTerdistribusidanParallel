# Pub-Sub Log Aggregator dengan Idempotent Consumer dan Deduplication

Sistem log aggregator berbasis Python yang menggunakan arsitektur publish-subscribe untuk mengumpulkan dan memproses event log secara efisien. Sistem ini dirancang untuk menangani event dari multiple publisher secara concurrent, dengan fitur idempotency untuk mencegah pemrosesan duplikasi dan deduplication untuk menjamin konsistensi data, serta mendukung at-least-once delivery semantics.

## Arsitektur Sistem

Sistem ini terdiri dari komponen utama berikut:

- **Publisher**: Client eksternal yang mengirim event melalui HTTP POST
- **API Gateway**: Endpoint FastAPI yang menerima dan memvalidasi event
- **Async Queue**: Buffer in-memory untuk decoupling publisher dan consumer
- **Idempotent Consumer**: Background task yang memproses event dengan cek duplikasi
- **Dedup Store**: Database SQLite untuk penyimpanan persistent event unik

Alur data:
1. Publisher mengirim event ke POST /publish
2. Event divalidasi dan dimasukkan ke async queue
3. Consumer mengambil event dari queue
4. Consumer cek apakah event duplikat
5. Jika unik, event disimpan ke dedup store
6. Statistics diperbarui secara real-time

```
[Publisher] → POST /publish → [FastAPI] → [Queue] → [Consumer] → [Dedup Store]
```

## Teknologi yang Digunakan

- **Python 3.11**: Bahasa pemrograman utama
- **FastAPI**: Framework web untuk REST API dengan async support
- **SQLite**: Database embedded untuk persistent deduplication
- **Pydantic**: Library untuk validasi dan serialisasi data
- **asyncio**: Library untuk asynchronous programming
- **Docker**: Containerization untuk deployment yang konsisten

## Cara Menjalankan Aplikasi

### Menggunakan Docker

1. Build image:
   ```bash
   docker build -t uts-aggregator .
   ```
   Command ini membuat Docker image bernama `uts-aggregator` dari Dockerfile.

2. Run container:
   ```bash
   docker run -p 8080:8080 uts-aggregator
   ```
   Command ini menjalankan container dan memetakan port 8080 host ke port 8080 container.

Aplikasi akan berjalan di `http://localhost:8080`.

## Endpoint API

### POST /publish
Mengirim event baru untuk diproses.
- **Input**: JSON array atau object event
- **Output**: Status accepted dengan count dan queue size

### GET /events
Mengambil event yang sudah diproses.
- **Parameter**: `topic` (optional) untuk filter per topic
- **Output**: List event dengan metadata

### GET /stats
Mendapatkan statistik sistem real-time.
- **Output**: Metrics received, processed, duplicates, uptime, dll.

## Contoh Request

### Event JSON Format
```json
{
  "topic": "orders",
  "event_id": "order-123-v1",
  "timestamp": "2024-04-21T10:30:00Z",
  "source": "order-service",
  "payload": {
    "order_id": "12345",
    "amount": 500.00,
    "currency": "USD"
  }
}
```

### POST /publish Example
```bash
curl -X POST http://localhost:8080/publish \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "orders",
    "event_id": "order-123",
    "timestamp": "2024-04-21T10:30:00Z",
    "source": "order-service",
    "payload": {"order_id": "123", "amount": 500}
  }'
```

## Idempotency dan Deduplication

Sistem mencegah duplikasi event menggunakan composite key `(topic, event_id)`. Setiap event diperiksa sebelum disimpan; jika sudah ada, event diabaikan dan dicatat sebagai duplicate. Hal ini menjamin konsistensi meskipun terjadi duplicate delivery dari publisher.

## Delivery Semantics

Sistem menggunakan at-least-once delivery semantics, yang berarti event mungkin dikirim lebih dari sekali akibat retry atau failure. Namun, dengan idempotent consumer, event hanya diproses sekali, sehingga efek akhir sama dengan exactly-once.

## Pengujian

Sistem memiliki unit test menggunakan pytest untuk:
- Deduplication: Validasi event unik dan duplicate
- Persistensi: Dedup store survive restart
- Endpoint: API response validation

Jalankan test dengan:
```bash
pytest tests/test_aggregator.py -v
```

## Struktur Project

```
.
├── src/
│   ├── main.py          # FastAPI app dan endpoints
│   ├── models.py        # Event model (Pydantic)
│   ├── queue.py         # Async queue implementation
│   ├── consumer.py      # Idempotent consumer logic
│   ├── storage.py       # SQLite dedup store
│   └── stats.py         # Statistics tracking
├── tests/
│   └── test_aggregator.py  # Unit tests
├── Dockerfile          # Container config
├── requirements.txt    # Python dependencies
└── README.md           # Dokumentasi ini
```

## Video Demo

Video demo sistem tersedia di YouTube: 

## Catatan dan Asumsi

- Deduplication berdasarkan kombinasi `(topic, event_id)` yang unik global
- Sistem berjalan lokal dalam Docker tanpa external service
- Event timestamp menggunakan format ISO8601
- Queue size terbatas untuk mencegah memory exhaustion
