"""WhatsApp webhook endpoints - verification and incoming messages."""

import logging
import asyncio
import time
from collections import OrderedDict
from fastapi import APIRouter, Request, Response, Query

from app.config import get_settings
from app.services.whatsapp import mark_as_read
from app.services.groq_agent import process_message
from app.services.whatsapp import send_text_message
from app.services.document import handle_document_upload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])

# Message deduplication - keep last 1000 message IDs with timestamps
_processed_messages: OrderedDict[str, float] = OrderedDict()
MAX_DEDUP_SIZE = 1000
DEDUP_TTL_SECONDS = 300  # 5 minutes

# Lock to prevent concurrent processing of same message
_processing_locks: dict[str, asyncio.Lock] = {}


def _is_duplicate(message_id: str) -> bool:
    now = time.time()
    # Clean expired entries
    expired = [
        k for k, t in _processed_messages.items()
        if now - t > DEDUP_TTL_SECONDS
    ]
    for k in expired:
        _processed_messages.pop(k, None)

    if message_id in _processed_messages:
        return True
    _processed_messages[message_id] = now
    while len(_processed_messages) > MAX_DEDUP_SIZE:
        _processed_messages.popitem(last=False)
    return False


@router.get("")
async def verify_webhook(
        hub_mode: str = Query(None, alias="hub.mode"),
        hub_verify_token: str = Query(None, alias="hub.verify_token"),
        hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Verify webhook with Meta."""
    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == settings.webhook_verify_token:
        logger.info("Webhook verified successfully")
        return Response(content=hub_challenge, media_type="text/plain")
    logger.warning(f"Webhook verification failed: mode={hub_mode}")
    return Response(content="Forbidden", status_code=403)


@router.post("")
async def handle_webhook(request: Request):
    """Handle incoming WhatsApp messages."""
    body = await request.json()

    # Extract messages from the webhook payload
    try:
        entries = body.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})

                # Skip status-only updates (delivered, read, etc.)
                if "messages" not in value:
                    continue

                messages = value.get("messages", [])

                for message in messages:
                    message_id = message.get("id", "")
                    wa_id = message.get("from", "")
                    msg_type = message.get("type", "")

                    if not message_id or not wa_id:
                        continue

                    # Skip duplicates
                    if _is_duplicate(message_id):
                        logger.debug(
                            f"Skipping duplicate message: {message_id}")
                        continue

                    # Mark as read (fire and forget)
                    asyncio.create_task(mark_as_read(message_id))

                    # Process message with lock to prevent double processing
                    asyncio.create_task(
                        _safe_process(wa_id, message, msg_type, message_id))

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)

    # Always return 200 to Meta
    return Response(status_code=200)


async def _safe_process(wa_id: str, message: dict, msg_type: str,
                        message_id: str):
    """Process a message with a per-message lock to prevent double processing."""
    if message_id not in _processing_locks:
        _processing_locks[message_id] = asyncio.Lock()
    lock = _processing_locks[message_id]

    if lock.locked():
        logger.debug(f"Message {message_id} already being processed, skipping")
        return

    async with lock:
        await _process_incoming(wa_id, message, msg_type)

    # Cleanup lock after processing
    _processing_locks.pop(message_id, None)


async def _process_incoming(wa_id: str, message: dict, msg_type: str):
    """Process an incoming message and respond."""
    try:
        user_text = ""
        media_context = None

        if msg_type == "text":
            user_text = message.get("text", {}).get("body", "")

        elif msg_type == "image":
            image = message.get("image", {})
            media_id = image.get("id", "")
            caption = image.get("caption", "")
            mime_type = image.get("mime_type", "image/jpeg")

            # Download and save the image
            doc_result = await handle_document_upload(wa_id, media_id,
                                                      mime_type)
            if doc_result.get("success"):
                media_context = f"File saved at: {doc_result['file_path']}. This appears to be a driver's license photo."
            else:
                media_context = "The customer tried to send an image but it failed to download."

            user_text = caption

        elif msg_type == "document":
            doc = message.get("document", {})
            media_id = doc.get("id", "")
            caption = doc.get("caption", "")
            mime_type = doc.get("mime_type", "application/pdf")
            filename = doc.get("filename", "document")

            doc_result = await handle_document_upload(wa_id, media_id,
                                                      mime_type)
            if doc_result.get("success"):
                media_context = f"Document '{filename}' saved at: {doc_result['file_path']}."
            else:
                media_context = f"The customer tried to send a document '{filename}' but it failed to download."

            user_text = caption

        elif msg_type in ("audio", "video", "sticker", "location", "contacts"):
            user_text = f"[Sent a {msg_type} message]"

        elif msg_type == "interactive":
            interactive = message.get("interactive", {})
            if interactive.get("type") == "button_reply":
                user_text = interactive.get("button_reply",
                                            {}).get("title", "")
            elif interactive.get("type") == "list_reply":
                user_text = interactive.get("list_reply", {}).get("title", "")

        elif msg_type == "reaction":
            # Ignore reactions
            return

        else:
            user_text = f"[Unsupported message type: {msg_type}]"

        if not user_text and not media_context:
            return

        # Process through the AI agent
        reply = await process_message(wa_id, user_text, media_context)

        # Send reply (split long messages)
        if len(reply) > 4096:
            chunks = [reply[i:i + 4096] for i in range(0, len(reply), 4096)]
            for chunk in chunks:
                await send_text_message(wa_id, chunk)
        else:
            await send_text_message(wa_id, reply)

    except Exception as e:
        logger.error(f"Error processing message from {wa_id}: {e}",
                     exc_info=True)
        try:
            await send_text_message(
                wa_id,
                "Sorry, I encountered an error processing your message. Please try again."
            )
        except Exception:
            pass
