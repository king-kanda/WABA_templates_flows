import logging
from app.database import fetch_one, execute

logger = logging.getLogger(__name__)


async def get_or_create_customer(wa_id: str, name: str | None = None) -> dict:
    """Get existing customer or create a new one."""
    customer = await fetch_one("SELECT * FROM customers WHERE wa_id = ?",
                               (wa_id, ))
    if customer:
        # Update name if provided and currently null
        if name and not customer.get("name"):
            await execute("UPDATE customers SET name = ? WHERE wa_id = ?",
                          (name, wa_id))
            customer = await fetch_one(
                "SELECT * FROM customers WHERE wa_id = ?", (wa_id, ))
        return customer

    customer_id = await execute(
        "INSERT INTO customers (wa_id, name) VALUES (?, ?)", (wa_id, name))
    logger.info(f"Created new customer: wa_id={wa_id}, name={name}")
    return await fetch_one("SELECT * FROM customers WHERE id = ?",
                           (customer_id, ))


async def get_customer_by_wa_id(wa_id: str) -> dict | None:
    """Get a customer by WhatsApp ID."""
    return await fetch_one("SELECT * FROM customers WHERE wa_id = ?",
                           (wa_id, ))


async def update_customer_license_status(wa_id: str, verified: bool = True):
    """Mark customer's license as verified."""
    await execute(
        "UPDATE customers SET license_verified = ? WHERE wa_id = ?",
        (1 if verified else 0, wa_id),
    )
    logger.info(f"Updated license status for {wa_id}: verified={verified}")


async def get_all_customers() -> list[dict]:
    """Get all customers."""
    from app.database import fetch_all
    return await fetch_all("SELECT * FROM customers ORDER BY created_at DESC")
