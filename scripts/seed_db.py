"""Seed database with realistic e-commerce test data."""

import asyncio
import random
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, execute_write


# Sample data
FIRST_NAMES = ["John", "Jane", "Mike", "Sarah", "David", "Emma", "Chris", "Lisa", "Tom", "Anna",
               "James", "Mary", "Robert", "Jennifer", "Michael", "Linda", "William", "Barbara",
               "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Karen", "Charles", "Nancy"]

LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
              "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
              "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Thompson"]

PRODUCT_NAMES = {
    "electronics": ["Laptop", "Smartphone", "Tablet", "Headphones", "Smartwatch", "Camera",
                    "Monitor", "Keyboard", "Mouse", "Webcam", "Speaker", "Charger", "USB Hub",
                    "External Drive", "Router", "Printer", "Microphone", "Gaming Console"],
    "clothing": ["T-Shirt", "Jeans", "Jacket", "Dress", "Sweater", "Shorts", "Hoodie",
                 "Sneakers", "Boots", "Sandals", "Hat", "Socks", "Gloves", "Scarf"],
    "food": ["Organic Apples", "Fresh Bread", "Milk", "Cheese", "Coffee Beans", "Tea",
             "Pasta", "Rice", "Olive Oil", "Honey", "Chocolate", "Cookies", "Cereal"],
    "books": ["Fiction Novel", "Programming Book", "Cookbook", "Biography", "Self-Help Book",
              "History Book", "Science Book", "Art Book", "Travel Guide", "Dictionary"],
    "home": ["Lamp", "Pillow", "Blanket", "Towel", "Cutting Board", "Coffee Maker",
             "Blender", "Vacuum", "Fan", "Clock", "Mirror", "Plant Pot", "Candle"]
}

STATUSES = {
    "user": ["active", "inactive", "suspended"],
    "order": ["pending", "completed", "cancelled"]
}


def random_date(start_days_ago: int, end_days_ago: int = 0) -> datetime:
    """Generate random datetime between start_days_ago and end_days_ago."""
    start = datetime.now() - timedelta(days=start_days_ago)
    end = datetime.now() - timedelta(days=end_days_ago)
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)


async def seed_users(count: int = 50):
    """Create random users."""
    print(f"Creating {count} users...")
    user_ids = []

    for i in range(count):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        email = f"{first.lower()}.{last.lower()}{i}@example.com"
        name = f"{first} {last}"
        status = random.choices(
            STATUSES["user"],
            weights=[70, 20, 10]  # 70% active, 20% inactive, 10% suspended
        )[0]
        created_at = random_date(365, 0)  # Within last year

        user_id = await execute_write(
            "INSERT INTO users (email, name, status, created_at) VALUES (?, ?, ?, ?)",
            [email, name, status, created_at]
        )
        user_ids.append(user_id)

    print(f"Created {len(user_ids)} users")
    return user_ids


async def seed_products(count: int = 100):
    """Create random products."""
    print(f"Creating {count} products...")
    product_ids = []

    for category, items in PRODUCT_NAMES.items():
        for i in range(count // 5):  # Distribute evenly across categories
            name = random.choice(items)
            # Add variant if duplicate
            if i > 0:
                name = f"{name} {random.choice(['Pro', 'Plus', 'Deluxe', 'Premium', 'Standard'])}"

            price = round(random.uniform(9.99, 999.99), 2)
            in_stock = random.choice([1, 1, 1, 0])  # 75% in stock
            created_at = random_date(180, 0)  # Within last 6 months

            product_id = await execute_write(
                "INSERT INTO products (name, price, category, in_stock, created_at) VALUES (?, ?, ?, ?, ?)",
                [name, price, category, in_stock, created_at]
            )
            product_ids.append(product_id)

    print(f"Created {len(product_ids)} products")
    return product_ids


async def seed_orders(user_ids: list, product_ids: list, count: int = 200):
    """Create random orders with items."""
    print(f"Creating {count} orders...")
    order_count = 0
    item_count = 0

    for _ in range(count):
        user_id = random.choice(user_ids)
        status = random.choices(
            STATUSES["order"],
            weights=[20, 70, 10]  # 20% pending, 70% completed, 10% cancelled
        )[0]
        created_at = random_date(90, 0)  # Within last 3 months

        # Create order items
        num_items = random.randint(1, 5)
        items = []
        total = 0.0

        for _ in range(num_items):
            product_id = random.choice(product_ids)
            quantity = random.randint(1, 3)
            # Get product price (simplified - just generate realistic price)
            unit_price = round(random.uniform(9.99, 299.99), 2)
            items.append((product_id, quantity, unit_price))
            total += quantity * unit_price

        total = round(total, 2)

        # Insert order
        order_id = await execute_write(
            "INSERT INTO orders (user_id, total, status, created_at) VALUES (?, ?, ?, ?)",
            [user_id, total, status, created_at]
        )
        order_count += 1

        # Insert order items
        for product_id, quantity, unit_price in items:
            await execute_write(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                [order_id, product_id, quantity, unit_price]
            )
            item_count += 1

    print(f"Created {order_count} orders with {item_count} total items")


async def main():
    """Main seeding function."""
    print("Initializing database...")
    await init_db()

    print("\nSeeding database with test data...")
    user_ids = await seed_users(50)
    product_ids = await seed_products(100)
    await seed_orders(user_ids, product_ids, 200)

    print("\nDatabase seeding complete!")
    print("\nDatabase summary:")
    print("- 50 users (mix of active, inactive, suspended)")
    print("- 100 products across 5 categories")
    print("- 200 orders with ~500 order items")
    print("\nYou can now start the server and query the data!")


if __name__ == "__main__":
    asyncio.run(main())
