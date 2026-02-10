import logging
import os
from datetime import datetime
from app.services.whatsapp import download_media, save_media_file
from app.services.customer import get_or_create_customer
from app.database import execute

logger = logging.getLogger(__name__)


async def handle_document_upload(wa_id: str,
                                 media_id: str,
                                 mime_type: str = "image/jpeg") -> dict:
    """Download and store a document (license photo) from WhatsApp."""
    # Download media
    media_data = await download_media(media_id)
    if not media_data:
        return {"error": "Failed to download the document"}

    # Determine file extension
    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "application/pdf": ".pdf",
    }
    ext = ext_map.get(mime_type, ".jpg")

    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"license_{timestamp}{ext}"

    # Save file
    file_path = await save_media_file(media_data, wa_id, filename)

    # Ensure customer exists
    customer = await get_or_create_customer(wa_id)

    # Record in database
    await execute(
        """INSERT INTO documents (customer_id, doc_type, file_path, wa_media_id)
           VALUES (?, ?, ?, ?)""",
        (customer["id"], "drivers_license", file_path, media_id),
    )

    logger.info(f"Document saved for {wa_id}: {file_path}")
    return {
        "success": True,
        "file_path": file_path,
        "doc_type": "drivers_license",
        "message": "Driver's license photo saved successfully",
    }


async def record_document(wa_id: str, doc_type: str, file_path: str) -> dict:
    """Record a document in the database (called by agent tool)."""
    customer = await get_or_create_customer(wa_id)
    await execute(
        """INSERT INTO documents (customer_id, doc_type, file_path)
           VALUES (?, ?, ?)""",
        (customer["id"], doc_type, file_path),
    )
    return {
        "success": True,
        "message": f"Document ({doc_type}) recorded for customer",
    }
