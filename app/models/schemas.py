from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


# --- Vehicle Schemas ---
class VehicleCreate(BaseModel):
    make: str
    model: str
    year: int = Field(ge=2015, le=2030)
    category: str = Field(pattern="^(economy|midsize|suv|luxury|bakkie)$")
    license_plate: str
    daily_rate: float = Field(gt=0)
    status: str = Field(default="available",
                        pattern="^(available|maintenance|retired)$")


class VehicleUpdate(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    category: Optional[str] = None
    license_plate: Optional[str] = None
    daily_rate: Optional[float] = None
    status: Optional[str] = None


class VehicleResponse(BaseModel):
    id: int
    make: str
    model: str
    year: int
    category: str
    license_plate: str
    daily_rate: float
    status: str


# --- Booking Schemas ---
class BookingCreate(BaseModel):
    customer_wa_id: str
    customer_name: str
    vehicle_id: int
    pickup_date: date
    return_date: date


class BookingResponse(BaseModel):
    id: int
    reference: str
    customer_id: int
    vehicle_id: int
    pickup_date: str
    return_date: str
    total_days: int
    total_price: float
    status: str


class BookingCancel(BaseModel):
    reference: str
    wa_id: str


# --- Customer Schemas ---
class CustomerResponse(BaseModel):
    id: int
    wa_id: str
    name: Optional[str]
    email: Optional[str]
    license_verified: bool


# --- Stats ---
class DashboardStats(BaseModel):
    total_vehicles: int
    available_vehicles: int
    total_bookings: int
    active_bookings: int
    total_customers: int
    total_revenue: float
