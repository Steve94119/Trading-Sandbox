import csv
import sqlite3
from pathlib import Path

from config import DB_PATH


class DatabaseManager:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    type TEXT NOT NULL,
                    side TEXT NOT NULL,
                    amount REAL NOT NULL,
                    price REAL NOT NULL,
                    total REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    total_value REAL NOT NULL,
                    cash REAL NOT NULL,
                    assets_value REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset TEXT NOT NULL,
                    type TEXT NOT NULL,
                    side TEXT NOT NULL,
                    amount REAL NOT NULL,
                    price REAL NOT NULL,
                    stop_loss REAL,
                    take_profit REAL,
                    status TEXT NOT NULL
                );
            """)
            conn.commit()

    def save_transaction(self, timestamp: str, asset: str, type_: str, side: str,
                          amount: float, price: float, total: float) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO transactions (timestamp, asset, type, side, amount, price, total) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (timestamp, asset, type_, side, amount, price, total),
            )
            conn.commit()
            return cur.lastrowid

    def save_snapshot(self, timestamp: str, total_value: float,
                      cash: float, assets_value: float) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO portfolio_snapshots (timestamp, total_value, cash, assets_value) "
                "VALUES (?, ?, ?, ?)",
                (timestamp, total_value, cash, assets_value),
            )
            conn.commit()
            return cur.lastrowid

    def save_order(self, asset: str, type_: str, side: str, amount: float,
                   price: float, stop_loss, take_profit, status: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO orders (asset, type, side, amount, price, stop_loss, take_profit, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (asset, type_, side, amount, price, stop_loss, take_profit, status),
            )
            conn.commit()
            return cur.lastrowid

    def get_history(self, limit: int = 100) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM transactions ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def export_to_csv(self, table: str, file_path: str) -> None:
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            if not rows:
                return
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(dict(row) for row in rows)