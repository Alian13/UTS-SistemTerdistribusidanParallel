import asyncio
import logging
from src.storage import dedup_store
from src.stats import stats_tracker
from src.models import Event

logger = logging.getLogger(__name__)

class IdempotentConsumer:
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.is_running = False
    
    async def consume(self):
        self.is_running = True
        logger.info("Consumer started")
        
        while self.is_running:
            try:
                event = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                
                # 🔥 FIX: gunakan INSERT langsung (atomic dedup)
                success = dedup_store.store_event(
                    topic=event.topic,
                    event_id=event.event_id,
                    timestamp=event.timestamp.isoformat(),
                    source=event.source,
                    payload=event.payload
                )
                
                if success:
                    stats_tracker.record_processed(event.topic)
                    logger.info(f"Event processed: topic={event.topic}, event_id={event.event_id}")
                else:
                    stats_tracker.record_duplicate()
                    logger.info(f"Duplicate detected: topic={event.topic}, event_id={event.event_id}")
                
                self.queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in consumer: {e}")
                self.queue.task_done()
    
    def stop(self):
        self.is_running = False
        logger.info("Consumer stopped")


consumer = None

async def start_consumer(queue: asyncio.Queue):
    global consumer
    consumer = IdempotentConsumer(queue)
    await consumer.consume()

def stop_consumer():
    global consumer
    if consumer:
        consumer.stop()