"""Seed database with realistic e-commerce test data."""

import asyncio
import random
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from faker import Faker
from app.database import init_db, execute_write


# Initialize Faker
fake = Faker()

CATEGORIES = ["electronics", "clothing", "food", "books", "home"]

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


async def seed_users(count: int = 10000):
    """Create random users."""
    print(f"Creating {count} users...")
    user_ids = []

    for i in range(count):
        if i % 1000 == 0:
            print(f"  Created {i} users...")

        email = fake.unique.email()
        name = fake.name()
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


async def seed_products(count: int = 5000):
    """Create random products."""
    print(f"Creating {count} products...")
    product_ids = []

    for i in range(count):
        if i % 500 == 0:
            print(f"  Created {i} products...")

        category = random.choice(CATEGORIES)

        # Generate product name and description based on category
        if category == "electronics":
            name = f"{fake.word().capitalize()} {random.choice(['Laptop', 'Phone', 'Tablet', 'Watch', 'Camera', 'Monitor'])}"
            description = f"{fake.sentence()} Features include {fake.bs()}. {fake.catch_phrase()}. {fake.text(max_nb_chars=200)}"
        elif category == "clothing":
            name = f"{fake.color_name()} {random.choice(['Shirt', 'Jeans', 'Jacket', 'Dress', 'Sweater', 'Shoes'])}"
            description = f"Stylish {name.lower()}. {fake.sentence()} Made with {fake.word()} material. {fake.text(max_nb_chars=200)}"
        elif category == "food":
            name = f"{random.choice(['Organic', 'Fresh', 'Premium'])} {fake.word().capitalize()}"
            description = f"Delicious {name.lower()}. {fake.sentence()} {fake.text(max_nb_chars=200)}"
        elif category == "books":
            name = fake.catch_phrase()
            description = f"By {fake.name()}. {fake.text(max_nb_chars=300)} Published {fake.year()}."
        else:  # home
            name = f"{fake.word().capitalize()} {random.choice(['Set', 'Collection', 'Bundle'])}"
            description = f"Quality home product. {fake.sentence()} {fake.text(max_nb_chars=200)}"

        price = round(random.uniform(9.99, 999.99), 2)
        in_stock = random.choice([1, 1, 1, 0])  # 75% in stock
        created_at = random_date(180, 0)  # Within last 6 months

        product_id = await execute_write(
            "INSERT INTO products (name, description, price, category, in_stock, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            [name, description, price, category, in_stock, created_at]
        )
        product_ids.append(product_id)

    print(f"Created {len(product_ids)} products")
    return product_ids


async def seed_orders(user_ids: list, product_ids: list, count: int = 150000):
    """Create random orders with items."""
    print(f"Creating {count} orders...")
    order_count = 0
    item_count = 0

    for i in range(count):
        if i % 5000 == 0:
            print(f"  Created {i} orders with {item_count} items...")

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

    print("\nSeeding database with large test dataset (target: ~200 MB)...")
    print("This may take several minutes...\n")

    user_ids = await seed_users(10000)
    product_ids = await seed_products(5000)
    await seed_orders(user_ids, product_ids, 150000)

    print("\nDatabase seeding complete!")
    print("\nDatabase summary:")
    print("- 10,000 users (mix of active, inactive, suspended)")
    print("- 5,000 products across 5 categories with descriptions")
    print("- 150,000 orders with ~375,000 order items")
    print("\nYou can now start the server and query the data!")


if __name__ == "__main__":
    asyncio.run(main())
