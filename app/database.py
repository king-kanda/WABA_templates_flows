import aiosqlite
import os
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)

_db_connection: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db_connection
    if _db_connection is None:
        settings = get_settings()
        os.makedirs(os.path.dirname(settings.database_path), exist_ok=True)
        _db_connection = await aiosqlite.connect(settings.database_path)
        _db_connection.row_factory = aiosqlite.Row
        await _db_connection.execute("PRAGMA journal_mode=WAL")
        await _db_connection.execute("PRAGMA foreign_keys=ON")
    return _db_connection


async def close_db():
    global _db_connection
    if _db_connection:
        await _db_connection.close()
        _db_connection = None


async def fetch_all(query: str, params: tuple = ()) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def fetch_one(query: str, params: tuple = ()) -> dict | None:
    db = await get_db()
    cursor = await db.execute(query, params)
    row = await cursor.fetchone()
    return dict(row) if row else None


async def execute(query: str, params: tuple = ()) -> int:
    db = await get_db()
    cursor = await db.execute(query, params)
    await db.commit()
    return cursor.lastrowid


async def execute_many(query: str, params_list: list[tuple]):
    db = await get_db()
    await db.executemany(query, params_list)
    await db.commit()


async def create_tables():
    db = await get_db()

    await db.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            make TEXT NOT NULL,
            model TEXT NOT NULL,
            year INTEGER NOT NULL,
            category TEXT NOT NULL CHECK(category IN ('economy', 'midsize', 'suv', 'luxury', 'bakkie')),
            license_plate TEXT UNIQUE NOT NULL,
            daily_rate REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available', 'maintenance', 'retired')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wa_id TEXT UNIQUE NOT NULL,
            name TEXT,
            email TEXT,
            license_verified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT UNIQUE NOT NULL,
            customer_id INTEGER NOT NULL,
            vehicle_id INTEGER NOT NULL,
            pickup_date TEXT NOT NULL,
            return_date TEXT NOT NULL,
            total_days INTEGER NOT NULL,
            total_price REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'confirmed' CHECK(status IN ('confirmed', 'active', 'completed', 'cancelled')),
            pickup_reminder_sent INTEGER DEFAULT 0,
            return_reminder_sent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            doc_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            wa_media_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wa_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            tool_call_id TEXT,
            tool_calls TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_conversations_wa_id
        ON conversations(wa_id, created_at)
    """)

    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_bookings_customer
        ON bookings(customer_id)
    """)

    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_bookings_dates
        ON bookings(pickup_date, return_date)
    """)

    await db.commit()
    logger.info("Database tables created successfully")
