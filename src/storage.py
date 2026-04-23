import sqlite3
import logging
from pathlib import Path
from typing import Tuple, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class DeduplicationStore:
    def __init__(self, db_path: str = "data/dedup.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabel untuk menyimpan event yang telah diproses
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                event_id TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                source TEXT NOT NULL,
                payload TEXT NOT NULL,
                processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(topic, event_id)
            )
        """)
        
        # Index untuk performa lookup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_topic_event_id 
            ON processed_events(topic, event_id)
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")
    
    def is_duplicate(self, topic: str, event_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT 1 FROM processed_events WHERE topic = ? AND event_id = ?",
            (topic, event_id)
        )
        result = cursor.fetchone()
        conn.close()
        
        return result is not None
    
    def store_event(self, topic: str, event_id: str, timestamp: str, 
                   source: str, payload: dict) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO processed_events 
                (topic, event_id, timestamp, source, payload)
                VALUES (?, ?, ?, ?, ?)
            """, (topic, event_id, timestamp, source, json.dumps(payload)))
            
            conn.commit()
            conn.close()
            return True
            
        except sqlite3.IntegrityError:
            return False
        except Exception as e:
            logger.error(f"Error storing event: {e}")
            return False
    
    def get_events_by_topic(self, topic: str) -> list:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Tabel untuk menyimpan event yang telah diproses
        cursor.execute("""
            SELECT topic, event_id, timestamp, source, payload, processed_at
            FROM processed_events
            WHERE topic = ?
            ORDER BY processed_at DESC
        """, (topic,))
        
        rows = cursor.fetchall()
        conn.close()
        
        events = []
        for row in rows:
            events.append({
                "topic": row["topic"],
                "event_id": row["event_id"],
                "timestamp": row["timestamp"],
                "source": row["source"],
                "payload": json.loads(row["payload"]),
                "processed_at": row["processed_at"]
            })
        
        return events
    
    def get_all_topics(self) -> list:
        """Ambil list unik dari semua topics yang ada"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT topic FROM processed_events ORDER BY topic")
        topics = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return topics
    
    def get_stats(self) -> dict:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM processed_events")
        total_events = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT topic) FROM processed_events")
        unique_topics = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_events_stored": total_events,
            "unique_topics": unique_topics
        }
    
    def clear(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM processed_events")
        conn.commit()
        conn.close()
        logger.info("Database cleared")


dedup_store = DeduplicationStore()
