import logging
import secrets
import string
from datetime import datetime, date
from app.database import fetch_all, fetch_one, execute
from app.services.customer import get_or_create_customer

logger = logging.getLogger(__name__)


def _generate_reference() -> str:
    """Generate a booking reference like BK-A3F7."""
    chars = string.ascii_uppercase + string.digits
    code = "".join(secrets.choice(chars) for _ in range(4))
    return f"BK-{code}"


async def check_availability(
    pickup_date: str,
    return_date: str,
    category: str | None = None,
    vehicle_id: int | None = None,
) -> list[dict]:
    """Check which vehicles are available for the given dates."""
    # Validate dates
    try:
        p_date = datetime.strptime(pickup_date, "%Y-%m-%d").date()
        r_date = datetime.strptime(return_date, "%Y-%m-%d").date()
    except ValueError:
        return []

    if p_date >= r_date:
        return []

    if p_date < date.today():
        return []

    # Find vehicles NOT booked during the requested period
    query = """
        SELECT v.* FROM vehicles v
        WHERE v.status = 'available'
        AND v.id NOT IN (
            SELECT b.vehicle_id FROM bookings b
            WHERE b.status IN ('confirmed', 'active')
            AND b.pickup_date < ?
            AND b.return_date > ?
        )
    """
    params = [return_date, pickup_date]

    if category:
        query += " AND v.category = ?"
        params.append(category)

    if vehicle_id:
        query += " AND v.id = ?"
        params.append(vehicle_id)

    query += " ORDER BY v.category, v.daily_rate"

    return await fetch_all(query, tuple(params))


async def create_booking(
    wa_id: str,
    customer_name: str,
    vehicle_id: int,
    pickup_date: str,
    return_date: str,
) -> dict:
    """Create a new booking."""
    # Validate dates
    p_date = datetime.strptime(pickup_date, "%Y-%m-%d").date()
    r_date = datetime.strptime(return_date, "%Y-%m-%d").date()

    if p_date >= r_date:
        return {"error": "Return date must be after pickup date"}

    if p_date < date.today():
        return {"error": "Pickup date cannot be in the past"}

    total_days = (r_date - p_date).days
    if total_days > 30:
        return {"error": "Maximum rental period is 30 days"}

    # Check vehicle exists and is available
    vehicle = await fetch_one(
        "SELECT * FROM vehicles WHERE id = ? AND status = 'available'",
        (vehicle_id, ))
    if not vehicle:
        return {"error": "Vehicle not found or not available"}

    # Check not already booked for these dates
    conflict = await fetch_one(
        """SELECT id FROM bookings
           WHERE vehicle_id = ? AND status IN ('confirmed', 'active')
           AND pickup_date < ? AND return_date > ?""",
        (vehicle_id, return_date, pickup_date),
    )
    if conflict:
        return {"error": "Vehicle is already booked for those dates"}

    # Get/create customer
    customer = await get_or_create_customer(wa_id, customer_name)

    total_price = total_days * vehicle["daily_rate"]
    reference = _generate_reference()

    booking_id = await execute(
        """INSERT INTO bookings (reference, customer_id, vehicle_id, pickup_date,
           return_date, total_days, total_price, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed')""",
        (reference, customer["id"], vehicle_id, pickup_date, return_date,
         total_days, total_price),
    )

    logger.info(f"Booking created: {reference} for {wa_id}")

    return {
        "booking_id": booking_id,
        "reference": reference,
        "vehicle": f"{vehicle['year']} {vehicle['make']} {vehicle['model']}",
        "category": vehicle["category"],
        "license_plate": vehicle["license_plate"],
        "pickup_date": pickup_date,
        "return_date": return_date,
        "total_days": total_days,
        "total_price": total_price,
        "status": "confirmed",
    }


async def get_customer_bookings(wa_id: str) -> list[dict]:
    """Get all bookings for a customer."""
    return await fetch_all(
        """SELECT b.*, v.make, v.model, v.year, v.license_plate, v.category
           FROM bookings b
           JOIN vehicles v ON v.id = b.vehicle_id
           JOIN customers c ON c.id = b.customer_id
           WHERE c.wa_id = ?
           ORDER BY b.created_at DESC""",
        (wa_id, ),
    )


async def cancel_booking(reference: str, wa_id: str) -> dict:
    """Cancel a booking, verifying ownership."""
    booking = await fetch_one(
        """SELECT b.*, c.wa_id FROM bookings b
           JOIN customers c ON c.id = b.customer_id
           WHERE b.reference = ?""",
        (reference, ),
    )

    if not booking:
        return {"error": f"No booking found with reference {reference}"}

    if booking["wa_id"] != wa_id:
        return {"error": "This booking does not belong to you"}

    if booking["status"] == "cancelled":
        return {"error": "This booking is already cancelled"}

    if booking["status"] == "completed":
        return {"error": "Cannot cancel a completed booking"}

    await execute(
        "UPDATE bookings SET status = 'cancelled' WHERE reference = ?",
        (reference, ),
    )

    logger.info(f"Booking {reference} cancelled by {wa_id}")
    return {
        "success": True,
        "reference": reference,
        "message": "Booking cancelled successfully"
    }


async def get_all_bookings(status: str | None = None) -> list[dict]:
    """Get all bookings, optionally filtered by status."""
    if status:
        return await fetch_all(
            """SELECT b.*, v.make, v.model, v.year, v.license_plate,
                      c.wa_id, c.name as customer_name
               FROM bookings b
               JOIN vehicles v ON v.id = b.vehicle_id
               JOIN customers c ON c.id = b.customer_id
               WHERE b.status = ?
               ORDER BY b.created_at DESC""",
            (status, ),
        )
    return await fetch_all(
        """SELECT b.*, v.make, v.model, v.year, v.license_plate,
                  c.wa_id, c.name as customer_name
           FROM bookings b
           JOIN vehicles v ON v.id = b.vehicle_id
           JOIN customers c ON c.id = b.customer_id
           ORDER BY b.created_at DESC""")
