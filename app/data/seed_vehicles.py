"""Seed sample vehicle inventory."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.database import create_tables, get_db, close_db, execute, fetch_one

VEHICLES = [
    # Economy (R350/day)
    ("Toyota", "Starlet", 2024, "economy", "GP-STR-001", 350),
    ("Volkswagen", "Polo", 2023, "economy", "GP-POL-002", 350),
    ("Hyundai", "Grand i10", 2024, "economy", "GP-I10-003", 350),
    # Midsize (R550/day)
    ("Toyota", "Corolla", 2024, "midsize", "GP-COR-004", 550),
    ("Hyundai", "Elantra", 2023, "midsize", "GP-ELA-005", 550),
    ("Volkswagen", "Jetta", 2024, "midsize", "GP-JET-006", 550),
    # SUV (R750/day)
    ("Toyota", "RAV4", 2024, "suv", "GP-RAV-007", 750),
    ("Hyundai", "Tucson", 2023, "suv", "GP-TUC-008", 750),
    ("Kia", "Sportage", 2024, "suv", "GP-SPO-009", 750),
    # Luxury (R1200/day)
    ("BMW", "3 Series", 2024, "luxury", "GP-BMW-010", 1200),
    ("Mercedes-Benz", "C-Class", 2024, "luxury", "GP-MBC-011", 1200),
    # Bakkie (R650/day)
    ("Toyota", "Hilux", 2024, "bakkie", "GP-HIL-012", 650),
    ("Ford", "Ranger", 2023, "bakkie", "GP-RNG-013", 650),
]


async def seed():
    await create_tables()

    # Check if already seeded
    existing = await fetch_one("SELECT COUNT(*) as count FROM vehicles")
    if existing and existing["count"] > 0:
        print(
            f"Database already has {existing['count']} vehicles. Skipping seed."
        )
        return

    for make, model, year, category, plate, rate in VEHICLES:
        await execute(
            """INSERT INTO vehicles (make, model, year, category, license_plate, daily_rate)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (make, model, year, category, plate, rate),
        )
        print(f"  Added: {year} {make} {model} ({category}) - R{rate}/day")

    print(f"\nSeeded {len(VEHICLES)} vehicles successfully!")
    await close_db()


if __name__ == "__main__":
    asyncio.run(seed())
