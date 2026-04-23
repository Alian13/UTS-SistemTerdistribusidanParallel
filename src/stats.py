import logging
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)

class StatsTracker:
    def __init__(self):
        self.start_time = datetime.now()
        self.received_count = 0
        self.processed_count = 0
        self.duplicate_count = 0
        self.topics_counter: Dict[str, int] = {}
    
    def record_received(self):
        self.received_count += 1
    
    def record_processed(self, topic: str):
        self.processed_count += 1
        if topic not in self.topics_counter:
            self.topics_counter[topic] = 0
        self.topics_counter[topic] += 1
    
    def record_duplicate(self):
        self.duplicate_count += 1
    
    def get_stats(self) -> dict:
        now = datetime.now()
        uptime = (now - self.start_time).total_seconds()
        
        return {
            "received": self.received_count,
            "unique_processed": self.processed_count,
            "duplicate_dropped": self.duplicate_count,
            "topics": self.topics_counter,
            "uptime_seconds": round(uptime, 2),
            "timestamp": now.isoformat()
        }
    
    def reset(self):
        self.start_time = datetime.now()
        self.received_count = 0
        self.processed_count = 0
        self.duplicate_count = 0
        self.topics_counter = {}
        logger.info("Stats reset")


stats_tracker = StatsTracker()
