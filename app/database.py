"""Database layer for async SQLite operations."""

import aiosqlite
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
import logging

from app.config import settings

logger = logging.getLogger(__name__)


# SQL schema for e-commerce database
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'inactive', 'suspended')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    price REAL NOT NULL CHECK(price >= 0),
    category TEXT,
    in_stock BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    total REAL NOT NULL CHECK(total >= 0),
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'completed', 'cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price REAL NOT NULL CHECK(unit_price >= 0),
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_in_stock ON products(in_stock);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);
"""


@asynccontextmanager
async def get_db():
    """Get async database connection context manager."""
    conn = await aiosqlite.connect(settings.database_path)
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
    finally:
        await conn.close()


async def init_db():
    """Initialize database with schema."""
    async with get_db() as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()
        logger.info("Database initialized successfully")


async def execute_query(sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
    """Execute a SELECT query and return results as list of dicts."""
    if params is None:
        params = []

    async with get_db() as db:
        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            # Convert Row objects to dicts
            return [dict(row) for row in rows]


async def execute_write(sql: str, params: Optional[List[Any]] = None) -> int:
    """Execute an INSERT/UPDATE/DELETE query and return last row id."""
    if params is None:
        params = []

    async with get_db() as db:
        cursor = await db.execute(sql, params)
        await db.commit()
        return cursor.lastrowid


async def get_table_schema(table_name: str) -> List[Dict[str, Any]]:
    """Get schema information for a table."""
    sql = f"PRAGMA table_info({table_name})"
    async with get_db() as db:
        async with db.execute(sql) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_all_tables() -> List[str]:
    """Get list of all table names in the database."""
    sql = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    async with get_db() as db:
        async with db.execute(sql) as cursor:
            rows = await cursor.fetchall()
            return [row['name'] for row in rows]


# Database schema metadata for LLM prompts
DATABASE_SCHEMA_INFO = {
    "users": {
        "columns": ["id", "email", "name", "status", "created_at"],
        "description": "User accounts with status (active/inactive/suspended)"
    },
    "products": {
        "columns": ["id", "name", "description", "price", "category", "in_stock", "created_at"],
        "description": "Product catalog with pricing and inventory"
    },
    "orders": {
        "columns": ["id", "user_id", "total", "status", "created_at"],
        "description": "Customer orders with status (pending/completed/cancelled)"
    },
    "order_items": {
        "columns": ["id", "order_id", "product_id", "quantity", "unit_price"],
        "description": "Line items within orders"
    }
}


def get_schema_description() -> str:
    """Get formatted schema description for LLM prompts."""
    lines = ["Database schema:"]
    for table, info in DATABASE_SCHEMA_INFO.items():
        columns = ", ".join(info["columns"])
        lines.append(f"- {table} ({columns})")
        lines.append(f"  {info['description']}")
    return "\n".join(lines)
