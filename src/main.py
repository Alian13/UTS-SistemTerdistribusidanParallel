import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, Query
from pydantic import BaseModel

from src.models import Event
from src.queue import event_queue
from src.storage import dedup_store
from src.stats import stats_tracker
from src.consumer import IdempotentConsumer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

consumer_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer_task
    logger.info("Starting Log Aggregator...")
    
    consumer = IdempotentConsumer(event_queue)
    consumer_task = asyncio.create_task(consumer.consume())
    
    yield
    
    logger.info("Shutting down Log Aggregator...")
    if consumer_task:
        consumer.stop()
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass

app = FastAPI(
    title="Log Aggregator",
    description="Pub-Sub Log Aggregator dengan Idempotent Consumer dan Deduplication",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "service": "Log Aggregator",
        "version": "1.0.0"
    }

@app.post("/publish", tags=["Publisher"])
async def publish(
    events: List[Event] | Event
):
    
    if isinstance(events, Event):
        events = [events]
    
    if not events or len(events) == 0:
        return {"status": "rejected", "reason": "No events provided"}
    
    accepted_count = 0
    for event in events:
        try:
            await event_queue.put(event)
            stats_tracker.record_received()
            accepted_count += 1
            logger.info(f"Event accepted: topic={event.topic}, event_id={event.event_id}")
        except asyncio.QueueFull:
            logger.error(f"Queue full, event rejected: {event.event_id}")
            break
    
    return {
        "status": "accepted",
        "count": accepted_count,
        "queue_size": event_queue.qsize()
    }

@app.get("/events", tags=["Events"])
async def get_events(
    topic: Optional[str] = Query(None, description="Filter by topic")
):
    if topic:
        events = dedup_store.get_events_by_topic(topic)
        return {
            "topic": topic,
            "count": len(events),
            "events": events
        }
    else:
        all_topics = dedup_store.get_all_topics()
        all_events = []
        for t in all_topics:
            all_events.extend(dedup_store.get_events_by_topic(t))
        
        return {
            "total_events": len(all_events),
            "topics": all_topics,
            "events": all_events
        }

@app.get("/stats", tags=["Statistics"])
async def get_stats():
    app_stats = stats_tracker.get_stats()
    store_stats = dedup_store.get_stats()
    
    return {
        **app_stats,
        "store": store_stats,
        "queue_size": event_queue.qsize()
    }