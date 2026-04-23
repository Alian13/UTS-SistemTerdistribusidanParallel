import pytest
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

from src.models import Event
from src.storage import DeduplicationStore
from src.stats import StatsTracker
from src.queue import event_queue
from src.consumer import IdempotentConsumer


@pytest.fixture
def temp_db_path(tmp_path):
    return str(tmp_path / "test_dedup.db")

@pytest.fixture
def dedup_store_test(temp_db_path):
    store = DeduplicationStore(db_path=temp_db_path)
    yield store
    store.clear()

@pytest.fixture
def stats_tracker_test():
    tracker = StatsTracker()
    yield tracker
    tracker.reset()

@pytest.fixture
def sample_event():
    return Event(
        topic="test-topic",
        event_id="evt-001",
        timestamp=datetime.now(),
        source="test-publisher",
        payload={"message": "test payload", "value": 42}
    )


def test_dedup_single_event(dedup_store_test):
    result1 = dedup_store_test.store_event(
        topic="user-login",
        event_id="user-123-login-001",
        timestamp=datetime.now().isoformat(),
        source="auth-service",
        payload={"user_id": "123", "ip": "192.168.1.1"}
    )
    assert result1 is True, "First insert should succeed"
    
    is_dup = dedup_store_test.is_duplicate("user-login", "user-123-login-001")
    assert is_dup is True, "Event should be detected as duplicate"


def test_dedup_multiple_duplicates(dedup_store_test):
    event_id = "evt-multi-dup"
    topic = "payment"
    
    result1 = dedup_store_test.store_event(topic, event_id, 
                                          datetime.now().isoformat(), 
                                          "payment-svc", {"amount": 100})
    result2 = dedup_store_test.store_event(topic, event_id, 
                                          datetime.now().isoformat(), 
                                          "payment-svc", {"amount": 100})
    result3 = dedup_store_test.store_event(topic, event_id, 
                                          datetime.now().isoformat(), 
                                          "payment-svc", {"amount": 100})
    
    assert result1 is True, "First insert should succeed"
    assert result2 is False, "Second insert (duplicate) should fail"
    assert result3 is False, "Third insert (duplicate) should fail"


def test_dedup_store_persistence(temp_db_path):
    store1 = DeduplicationStore(db_path=temp_db_path)
    result1 = store1.store_event("orders", "order-001", 
                                datetime.now().isoformat(), 
                                "order-svc", {"total": 500})
    assert result1 is True
    
    # Check duplicate (same instance)
    is_dup1 = store1.is_duplicate("orders", "order-001")
    assert is_dup1 is True
    
    store2 = DeduplicationStore(db_path=temp_db_path)
    
    # Check duplicate (new instance, same db)
    is_dup2 = store2.is_duplicate("orders", "order-001")
    assert is_dup2 is True, "Dedup store should persist after 'restart'"
    
    result2 = store2.store_event("orders", "order-001", 
                                datetime.now().isoformat(), 
                                "order-svc", {"total": 500})
    assert result2 is False, "Duplicate prevention should work after restart"


def test_event_schema_validation():
    event = Event(
        topic="logs",
        event_id="log-123",
        timestamp=datetime.now(),
        source="app",
        payload={"level": "info"}
    )
    assert event.topic == "logs"
    assert event.event_id == "log-123"
    
    with pytest.raises(Exception):  # Pydantic ValidationError
        Event(
            topic="logs",
            event_id=None,  # Missing
            timestamp=datetime.now(),
            source="app",
            payload={}
        )


def test_event_schema_timestamp_iso8601(sample_event):
    iso_str = sample_event.timestamp.isoformat()
    assert "T" in iso_str
    
    parsed_time = datetime.fromisoformat(iso_str)
    assert isinstance(parsed_time, datetime)


def test_stats_consistency(dedup_store_test, stats_tracker_test):
    for i in range(5):
        stats_tracker_test.record_received()
    
    for i in range(3):
        stats_tracker_test.record_processed(f"topic-{i}")
    for i in range(2):
        stats_tracker_test.record_duplicate()
    
    stats = stats_tracker_test.get_stats()
    
    assert stats["received"] == 5
    assert stats["unique_processed"] == 3
    assert stats["duplicate_dropped"] == 2
    assert stats["received"] == stats["unique_processed"] + stats["duplicate_dropped"]


def test_stats_topics_counter(stats_tracker_test):
    stats_tracker_test.record_processed("orders")
    stats_tracker_test.record_processed("orders")
    stats_tracker_test.record_processed("payments")
    stats_tracker_test.record_processed("payments")
    stats_tracker_test.record_processed("payments")
    
    stats = stats_tracker_test.get_stats()
    
    assert stats["topics"]["orders"] == 2
    assert stats["topics"]["payments"] == 3
    assert sum(stats["topics"].values()) == 5


def test_get_events_by_topic(dedup_store_test):
    for i in range(3):
        dedup_store_test.store_event(
            topic="logs",
            event_id=f"log-{i}",
            timestamp=datetime.now().isoformat(),
            source="app",
            payload={"msg": f"message {i}"}
        )
    
    for i in range(2):
        dedup_store_test.store_event(
            topic="errors",
            event_id=f"err-{i}",
            timestamp=datetime.now().isoformat(),
            source="app",
            payload={"error": f"error {i}"}
        )
    
    logs_events = dedup_store_test.get_events_by_topic("logs")
    error_events = dedup_store_test.get_events_by_topic("errors")
    
    assert len(logs_events) == 3
    assert len(error_events) == 2
    assert all(e["topic"] == "logs" for e in logs_events)
    assert all(e["topic"] == "errors" for e in error_events)


def test_stress_large_batch(dedup_store_test, stats_tracker_test):
    import time
    
    total_events = 5000
    unique_event_ids = set()
    duplicate_count = 0
    
    event_list = []
    for i in range(total_events):
        event_id = f"stress-{i % 4000}"
        event_list.append((
            "stress-test",
            event_id,
            datetime.now().isoformat(),
            "stress-generator",
            {"index": i}
        ))
    
    # Process events
    start_time = time.time()
    
    for topic, event_id, timestamp, source, payload in event_list:
        result = dedup_store_test.store_event(topic, event_id, timestamp, source, payload)
        if result:
            stats_tracker_test.record_processed(topic)
        else:
            stats_tracker_test.record_duplicate()
            duplicate_count += 1
    
    elapsed_time = time.time() - start_time
    
    stats = stats_tracker_test.get_stats()
    assert stats["unique_processed"] == 4000, "Should process 4000 unique events"
    assert stats["duplicate_dropped"] == 1000, "Should drop 1000 duplicates"
    assert elapsed_time < 30.0, "Should process 5000 events in < 30 seconds"
    
    print(f"\n✓ Processed 5000 events in {elapsed_time:.2f}s")
    print(f"  - Unique: {stats['unique_processed']}")
    print(f"  - Duplicates: {stats['duplicate_dropped']}")
    print(f"  - Throughput: {total_events/elapsed_time:.0f} events/sec")


# ==================== TEST 7: Consumer Idempotency ====================

@pytest.mark.asyncio
async def test_consumer_idempotency():
    """
    TEST 7: Consumer idempotency - event yang sama tidak diproses 2x
    """
    # Setup
    test_queue = asyncio.Queue()
    temp_db = "data/test_consumer_idempotency.db"
    store = DeduplicationStore(db_path=temp_db)
    consumer = IdempotentConsumer(test_queue)
    
    # Create task untuk consumer (run di background)
    consumer_task = asyncio.create_task(consumer.consume())
    
    try:
        # Put same event 3 times ke queue
        event = Event(
            topic="idempotency-test",
            event_id="idem-001",
            timestamp=datetime.now(),
            source="test",
            payload={"data": "test"}
        )
        
        for _ in range(3):
            await test_queue.put(event)
        
        # Wait untuk consumer process
        await asyncio.sleep(0.5)
        
        # Check: hanya 1 event yang di-store
        events = store.get_events_by_topic("idempotency-test")
        assert len(events) == 1, "Should store only 1 event despite 3 puts"
        
    finally:
        consumer.stop()
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
        
        store.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
