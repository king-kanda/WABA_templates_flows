import logging
from app.database import fetch_all, fetch_one

logger = logging.getLogger(__name__)


async def get_all_vehicles(status: str | None = None) -> list[dict]:
    """Get all vehicles, optionally filtered by status."""
    if status:
        return await fetch_all("SELECT * FROM vehicles WHERE status = ?",
                               (status, ))
    return await fetch_all("SELECT * FROM vehicles ORDER BY category, make")


async def get_vehicle_by_id(vehicle_id: int) -> dict | None:
    """Get a specific vehicle by ID."""
    return await fetch_one("SELECT * FROM vehicles WHERE id = ?",
                           (vehicle_id, ))


async def get_vehicles_by_category(category: str) -> list[dict]:
    """Get all available vehicles in a category."""
    return await fetch_all(
        "SELECT * FROM vehicles WHERE category = ? AND status = 'available'",
        (category, ),
    )


async def get_vehicle_details_formatted(vehicle_id: int) -> str:
    """Get vehicle details as a formatted string for the agent."""
    vehicle = await get_vehicle_by_id(vehicle_id)
    if not vehicle:
        return f"No vehicle found with ID {vehicle_id}"

    return (f"Vehicle ID: {vehicle['id']}\n"
            f"Make: {vehicle['make']}\n"
            f"Model: {vehicle['model']}\n"
            f"Year: {vehicle['year']}\n"
            f"Category: {vehicle['category']}\n"
            f"License Plate: {vehicle['license_plate']}\n"
            f"Daily Rate: R{vehicle['daily_rate']:.2f}\n"
            f"Status: {vehicle['status']}")
