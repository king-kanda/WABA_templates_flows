import asyncio
import logging
from datetime import datetime, timedelta
from app.database import fetch_all, execute
from app.services.whatsapp import send_text_message

logger = logging.getLogger(__name__)

REMINDER_INTERVAL_SECONDS = 3600  # 1 hour


async def send_pickup_reminders():
    """Send pickup reminders for bookings with pickup tomorrow."""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    bookings = await fetch_all(
        """SELECT b.*, c.wa_id, v.make, v.model, v.year
           FROM bookings b
           JOIN customers c ON c.id = b.customer_id
           JOIN vehicles v ON v.id = b.vehicle_id
           WHERE b.pickup_date = ?
           AND b.status = 'confirmed'
           AND b.pickup_reminder_sent = 0""",
        (tomorrow, ),
    )

    for booking in bookings:
        try:
            message = (
                f"Hi! Just a friendly reminder that your car rental pickup is tomorrow.\n\n"
                f"Booking: {booking['reference']}\n"
                f"Vehicle: {booking['year']} {booking['make']} {booking['model']}\n"
                f"Pickup Date: {booking['pickup_date']}\n"
                f"Return Date: {booking['return_date']}\n\n"
                f"Please remember to bring your driver's license and credit card for the deposit.\n\n"
                f"See you at DriveEasy Car Rentals, 45 Main Road, Sandton!")
            await send_text_message(booking["wa_id"], message)
            await execute(
                "UPDATE bookings SET pickup_reminder_sent = 1 WHERE id = ?",
                (booking["id"], ),
            )
            logger.info(
                f"Pickup reminder sent for booking {booking['reference']}")
        except Exception as e:
            logger.error(
                f"Failed to send pickup reminder for {booking['reference']}: {e}"
            )


async def send_return_reminders():
    """Send return reminders for bookings with return tomorrow."""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    bookings = await fetch_all(
        """SELECT b.*, c.wa_id, v.make, v.model, v.year
           FROM bookings b
           JOIN customers c ON c.id = b.customer_id
           JOIN vehicles v ON v.id = b.vehicle_id
           WHERE b.return_date = ?
           AND b.status IN ('confirmed', 'active')
           AND b.return_reminder_sent = 0""",
        (tomorrow, ),
    )

    for booking in bookings:
        try:
            message = (
                f"Hi! This is a reminder that your car rental return is due tomorrow.\n\n"
                f"Booking: {booking['reference']}\n"
                f"Vehicle: {booking['year']} {booking['make']} {booking['model']}\n"
                f"Return Date: {booking['return_date']}\n\n"
                f"Please return the vehicle with a full tank of fuel.\n"
                f"Late returns: R200/hour for the first 3 hours, then charged as an extra day.\n\n"
                f"DriveEasy Car Rentals, 45 Main Road, Sandton")
            await send_text_message(booking["wa_id"], message)
            await execute(
                "UPDATE bookings SET return_reminder_sent = 1 WHERE id = ?",
                (booking["id"], ),
            )
            logger.info(
                f"Return reminder sent for booking {booking['reference']}")
        except Exception as e:
            logger.error(
                f"Failed to send return reminder for {booking['reference']}: {e}"
            )


async def reminder_loop():
    """Background loop that checks for reminders every hour."""
    logger.info("Reminder background task started")
    while True:
        try:
            await send_pickup_reminders()
            await send_return_reminders()
        except Exception as e:
            logger.error(f"Reminder loop error: {e}")
        await asyncio.sleep(REMINDER_INTERVAL_SECONDS)
