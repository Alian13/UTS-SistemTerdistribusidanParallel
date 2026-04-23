import requests
import json
import time
import os
import random
import uuid
from datetime import datetime

# Configuration
AGGREGATOR_HOST = os.getenv("AGGREGATOR_HOST", "http://localhost:8080")
NUM_EVENTS = int(os.getenv("NUM_EVENTS", "1000"))
DUPLICATE_RATE = float(os.getenv("DUPLICATE_RATE", "0.2"))

def generate_events(num_events: int, duplicate_rate: float) -> list:
    topics = ["orders", "payments", "users", "inventory", "notifications"]
    sources = ["order-service", "payment-service", "user-service", "inventory-service"]
    
    unique_event_ids = set()
    events = []
    
    num_unique = int(num_events * (1 - duplicate_rate))
    num_duplicate = num_events - num_unique
    
    for i in range(num_unique):
        event_id = f"evt-{uuid.uuid4()}"
        unique_event_ids.add(event_id)
        
        events.append({
            "topic": random.choice(topics),
            "event_id": event_id,
            "timestamp": datetime.now().isoformat(),
            "source": random.choice(sources),
            "payload": {
                "index": i,
                "data": f"unique-event-{i}",
                "value": random.randint(1, 1000)
            }
        })
    
    for i in range(num_duplicate):
        duplicate_event_id = random.choice(list(unique_event_ids))
        
        events.append({
            "topic": random.choice(topics),
            "event_id": duplicate_event_id,
            "timestamp": datetime.now().isoformat(),
            "source": random.choice(sources),
            "payload": {
                "index": num_unique + i,
                "data": f"duplicate-event-{i}",
                "value": random.randint(1, 1000)
            }
        })
    
    random.shuffle(events)
    return events

def publish_events(events: list, batch_size: int = 100):
    url = f"{AGGREGATOR_HOST}/publish"
    headers = {"Content-Type": "application/json"}
    
    total_batches = (len(events) + batch_size - 1) // batch_size
    
    print(f"Publishing {len(events)} events in {total_batches} batches to {url}")
    print(f"  - Unique: ~{int(len(events) * (1 - DUPLICATE_RATE))}")
    print(f"  - Duplicates: ~{int(len(events) * DUPLICATE_RATE)}")
    
    start_time = time.time()
    
    for batch_num, i in enumerate(range(0, len(events), batch_size), 1):
        batch = events[i:i + batch_size]
        
        try:
            response = requests.post(url, json=batch, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"[{batch_num}/{total_batches}] Batch sent: {data['count']} events accepted, "
                      f"queue_size={data['queue_size']}")
            else:
                print(f"[{batch_num}/{total_batches}] Error: {response.status_code} - {response.text}")
        
        except Exception as e:
            print(f"[{batch_num}/{total_batches}] Exception: {e}")
        
        time.sleep(0.1)  # Small delay between batches
    
    elapsed = time.time() - start_time
    print(f"\nPublishing complete in {elapsed:.2f}s")
    print(f"Throughput: {len(events) / elapsed:.0f} events/sec")

def check_stats():
    url = f"{AGGREGATOR_HOST}/stats"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            stats = response.json()
            print("\n=== Aggregator Stats ===")
            print(f"Received: {stats['received']}")
            print(f"Unique Processed: {stats['unique_processed']}")
            print(f"Duplicate Dropped: {stats['duplicate_dropped']}")
            print(f"Queue Size: {stats['queue_size']}")
            print(f"Uptime: {stats['uptime_seconds']:.2f}s")
            print(f"Topics: {stats['topics']}")
        else:
            print(f"Error: {response.status_code}")
    except Exception as e:
        print(f"Error checking stats: {e}")

def main():
    print("Test Publisher for Log Aggregator")
    print("=" * 50)
    
    print("Waiting for aggregator to be ready...")
    for attempt in range(30):
        try:
            response = requests.get(f"{AGGREGATOR_HOST}/", timeout=2)
            if response.status_code == 200:
                print("Aggregator is ready!")
                break
        except:
            pass
        
        if attempt < 29:
            time.sleep(1)
    else:
        print("Timeout: Aggregator not ready")
        return
    
    events = generate_events(NUM_EVENTS, DUPLICATE_RATE)
    publish_events(events, batch_size=100)
    
    print("\nWaiting for events to be processed...")
    time.sleep(2)
    
    check_stats()

if __name__ == "__main__":
    main()
