"""Durable send queue.

Events wait here until the cloud has accepted them, so an internet outage or
a restart of the box loses nothing. One SQLite file in WAL mode; camera
threads push, the main loop sends and deletes.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Iterable, List, Tuple

MAX_ROWS = 2_000_000  # about a week of a busy store; oldest rows are dropped beyond this


class Outbox:
    def __init__(self, path: str, max_rows: int = MAX_ROWS) -> None:
        self.max_rows = max_rows
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, "
            "body TEXT NOT NULL, created REAL NOT NULL)"
        )
        self._db.execute("CREATE INDEX IF NOT EXISTS ix_items_kind ON items (kind, id)")
        self._db.commit()
        self.dropped = 0

    def push(self, kind: str, items: Iterable[dict]) -> int:
        rows = [(kind, json.dumps(i, separators=(",", ":")), time.time()) for i in items]
        if not rows:
            return 0
        with self._lock:
            self._db.executemany("INSERT INTO items (kind, body, created) VALUES (?, ?, ?)", rows)
            over = self._db.execute("SELECT COUNT(*) FROM items").fetchone()[0] - self.max_rows
            if over > 0:
                self._db.execute("DELETE FROM items WHERE id IN (SELECT id FROM items ORDER BY id LIMIT ?)", (over,))
                self.dropped += over
            self._db.commit()
        return len(rows)

    def peek(self, kind: str, limit: int) -> List[Tuple[int, dict]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, body FROM items WHERE kind = ? ORDER BY id LIMIT ?", (kind, limit)
            ).fetchall()
        return [(i, json.loads(b)) for i, b in rows]

    def delete(self, ids: Iterable[int]) -> None:
        ids = list(ids)
        if not ids:
            return
        with self._lock:
            self._db.executemany("DELETE FROM items WHERE id = ?", [(i,) for i in ids])
            self._db.commit()

    def count(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM items").fetchone()[0]

    def close(self) -> None:
        with self._lock:
            self._db.close()
