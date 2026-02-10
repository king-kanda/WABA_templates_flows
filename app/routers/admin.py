"""Admin API endpoints for vehicle CRUD, booking management, and stats."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from app.config import get_settings
from app.database import fetch_all, fetch_one, execute
from app.models.schemas import (
    VehicleCreate,
    VehicleUpdate,
    VehicleResponse,
    BookingCancel,
    CustomerResponse,
    DashboardStats,
)
from app.services.booking import get_all_bookings, cancel_booking
from app.services.customer import get_all_customers

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


async def verify_admin_key(x_api_key: str = Header(...)):
    settings = get_settings()
    if x_api_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return True


# --- Vehicles ---


@router.get("/vehicles")
async def list_vehicles(
        status: str | None = None,
        _auth: bool = Depends(verify_admin_key),
):
    if status:
        return await fetch_all(
            "SELECT * FROM vehicles WHERE status = ? ORDER BY id", (status, ))
    return await fetch_all("SELECT * FROM vehicles ORDER BY id")


@router.get("/vehicles/{vehicle_id}")
async def get_vehicle(vehicle_id: int,
                      _auth: bool = Depends(verify_admin_key)):
    vehicle = await fetch_one("SELECT * FROM vehicles WHERE id = ?",
                              (vehicle_id, ))
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


@router.post("/vehicles", status_code=201)
async def create_vehicle(vehicle: VehicleCreate,
                         _auth: bool = Depends(verify_admin_key)):
    vid = await execute(
        """INSERT INTO vehicles (make, model, year, category, license_plate, daily_rate, status)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (vehicle.make, vehicle.model, vehicle.year, vehicle.category,
         vehicle.license_plate, vehicle.daily_rate, vehicle.status),
    )
    return await fetch_one("SELECT * FROM vehicles WHERE id = ?", (vid, ))


@router.put("/vehicles/{vehicle_id}")
async def update_vehicle(
        vehicle_id: int,
        vehicle: VehicleUpdate,
        _auth: bool = Depends(verify_admin_key),
):
    existing = await fetch_one("SELECT * FROM vehicles WHERE id = ?",
                               (vehicle_id, ))
    if not existing:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    updates = {k: v for k, v in vehicle.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [vehicle_id]
    await execute(f"UPDATE vehicles SET {set_clause} WHERE id = ?",
                  tuple(values))
    return await fetch_one("SELECT * FROM vehicles WHERE id = ?",
                           (vehicle_id, ))


@router.delete("/vehicles/{vehicle_id}")
async def delete_vehicle(vehicle_id: int,
                         _auth: bool = Depends(verify_admin_key)):
    existing = await fetch_one("SELECT * FROM vehicles WHERE id = ?",
                               (vehicle_id, ))
    if not existing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    await execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id, ))
    return {"message": "Vehicle deleted"}


# --- Bookings ---


@router.get("/bookings")
async def list_bookings(
        status: str | None = None,
        _auth: bool = Depends(verify_admin_key),
):
    return await get_all_bookings(status)


@router.post("/bookings/cancel")
async def admin_cancel_booking(
        data: BookingCancel,
        _auth: bool = Depends(verify_admin_key),
):
    result = await cancel_booking(data.reference, data.wa_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# --- Customers ---


@router.get("/customers")
async def list_customers(_auth: bool = Depends(verify_admin_key)):
    return await get_all_customers()


# --- Stats ---


@router.get("/stats")
async def dashboard_stats(_auth: bool = Depends(verify_admin_key)):
    total_vehicles = await fetch_one("SELECT COUNT(*) as count FROM vehicles")
    available_vehicles = await fetch_one(
        "SELECT COUNT(*) as count FROM vehicles WHERE status = 'available'")
    total_bookings = await fetch_one("SELECT COUNT(*) as count FROM bookings")
    active_bookings = await fetch_one(
        "SELECT COUNT(*) as count FROM bookings WHERE status IN ('confirmed', 'active')"
    )
    total_customers = await fetch_one("SELECT COUNT(*) as count FROM customers"
                                      )
    revenue = await fetch_one(
        "SELECT COALESCE(SUM(total_price), 0) as total FROM bookings WHERE status != 'cancelled'"
    )

    return {
        "total_vehicles": total_vehicles["count"],
        "available_vehicles": available_vehicles["count"],
        "total_bookings": total_bookings["count"],
        "active_bookings": active_bookings["count"],
        "total_customers": total_customers["count"],
        "total_revenue": revenue["total"],
    }
