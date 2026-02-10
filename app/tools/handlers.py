"""Tool dispatch map and handler functions."""

import json
import logging
from app.services.booking import (
    check_availability,
    create_booking,
    get_customer_bookings,
    cancel_booking,
)
from app.services.vehicle import get_vehicle_details_formatted
from app.services.document import record_document

logger = logging.getLogger(__name__)


async def handle_check_availability(args: dict) -> str:
    vehicles = await check_availability(
        pickup_date=args["pickup_date"],
        return_date=args["return_date"],
        category=args.get("category"),
        vehicle_id=args.get("vehicle_id"),
    )
    if not vehicles:
        return json.dumps({
            "available":
            False,
            "message":
            "No vehicles available for the requested dates and criteria."
        })

    results = []
    for v in vehicles:
        results.append({
            "id": v["id"],
            "vehicle": f"{v['year']} {v['make']} {v['model']}",
            "category": v["category"],
            "license_plate": v["license_plate"],
            "daily_rate": v["daily_rate"],
        })
    return json.dumps({"available": True, "vehicles": results})


async def handle_create_booking(args: dict) -> str:
    result = await create_booking(
        wa_id=args["wa_id"],
        customer_name=args["customer_name"],
        vehicle_id=args["vehicle_id"],
        pickup_date=args["pickup_date"],
        return_date=args["return_date"],
    )
    return json.dumps(result)


async def handle_get_customer_bookings(args: dict) -> str:
    bookings = await get_customer_bookings(wa_id=args["wa_id"])
    if not bookings:
        return json.dumps({"bookings": [], "message": "No bookings found."})

    results = []
    for b in bookings:
        results.append({
            "reference": b["reference"],
            "vehicle": f"{b['year']} {b['make']} {b['model']}",
            "category": b["category"],
            "license_plate": b["license_plate"],
            "pickup_date": b["pickup_date"],
            "return_date": b["return_date"],
            "total_days": b["total_days"],
            "total_price": b["total_price"],
            "status": b["status"],
        })
    return json.dumps({"bookings": results})


async def handle_cancel_booking(args: dict) -> str:
    result = await cancel_booking(
        reference=args["reference"],
        wa_id=args["wa_id"],
    )
    return json.dumps(result)


async def handle_record_document(args: dict) -> str:
    result = await record_document(
        wa_id=args["wa_id"],
        doc_type=args["doc_type"],
        file_path=args["file_path"],
    )
    return json.dumps(result)


async def handle_get_vehicle_details(args: dict) -> str:
    details = await get_vehicle_details_formatted(vehicle_id=args["vehicle_id"]
                                                  )
    return details


# Dispatch map
TOOL_HANDLERS = {
    "check_availability": handle_check_availability,
    "create_booking": handle_create_booking,
    "get_customer_bookings": handle_get_customer_bookings,
    "cancel_booking": handle_cancel_booking,
    "record_document": handle_record_document,
    "get_vehicle_details": handle_get_vehicle_details,
}


async def dispatch_tool(tool_name: str, arguments: str) -> str:
    """Parse arguments and dispatch to the correct handler."""
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        args = json.loads(arguments)
        result = await handler(args)
        logger.info(f"Tool {tool_name} executed successfully")
        return result
    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {e}")
        return json.dumps({"error": str(e)})
