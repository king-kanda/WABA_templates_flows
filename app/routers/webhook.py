"""WhatsApp webhook endpoints - verification and incoming messages."""

import json
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
from app.services.conversation import save_message

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
            reply_type = interactive.get("type", "")

            if reply_type == "list_reply":
                list_reply = interactive.get("list_reply", {})
                picked_id = list_reply.get("id", "")
                picked_title = list_reply.get("title", "")
                picked_desc = list_reply.get("description", "")

                # Save the customer's pick
                user_pick = f"[Selected: {picked_title}]"
                if picked_desc:
                    user_pick += f" — {picked_desc}"
                await save_message(wa_id, "user", user_pick)

                # Send acknowledgment
                ack = (f"✅ *Great choice!*\n\n"
                       f"You selected: *{picked_title}*\n")
                if picked_desc:
                    ack += f"_{picked_desc}_\n"
                ack += (
                    f"\n⏳ We're now processing your *{picked_title}* request. "
                    f"Please hold on while we set things up for you…")
                await send_text_message(wa_id, ack)
                await save_message(wa_id, "assistant", ack)

                # Simulate processing delay then send follow-up
                await asyncio.sleep(3)

                followup = (
                    f"🔔 *Update on your request*\n\n"
                    f"Your *{picked_title}* request (ref: DE-{wa_id[-4:]}-{picked_id.upper()[:6]}) "
                    f"has been received and is being reviewed by our team.\n\n"
                    f"📋 *Next steps:*\n"
                    f"1️⃣ A DriveEasy agent will be assigned shortly\n"
                    f"2️⃣ You'll receive a confirmation within 24 hours\n"
                    f"3️⃣ We may reach out if we need more details\n\n"
                    f"Feel free to message us anytime if you have questions! 💬"
                )
                await send_text_message(wa_id, followup)
                await save_message(wa_id, "assistant", followup)
                return  # handled directly, skip AI agent

            elif reply_type == "button_reply":
                btn_reply = interactive.get("button_reply", {})
                picked_title = btn_reply.get("title", "")
                picked_id = btn_reply.get("id", "")

                # Save the customer's pick
                await save_message(wa_id, "user", f"[Tapped: {picked_title}]")

                ack = (f"✅ *Got it!*\n\n"
                       f"You tapped: *{picked_title}*\n\n"
                       f"⏳ Processing your selection, one moment please…")
                await send_text_message(wa_id, ack)
                await save_message(wa_id, "assistant", ack)

                await asyncio.sleep(2)

                followup = (
                    f"🔔 *All set!*\n\n"
                    f"Your *{picked_title}* action (ref: DE-{wa_id[-4:]}-{picked_id.upper()[:6]}) "
                    f"has been registered.\n\n"
                    f"We'll follow up with more details shortly. 💬")
                await send_text_message(wa_id, followup)
                await save_message(wa_id, "assistant", followup)
                return  # handled directly, skip AI agent

            elif reply_type == "nfm_reply":
                # WhatsApp Flow completion response
                nfm = interactive.get("nfm_reply", {})
                response_json_str = nfm.get("response_json", "{}")
                flow_name = nfm.get("name", "flow")
                flow_body = nfm.get("body", "")

                # Parse the flow response data
                try:
                    flow_data = json.loads(response_json_str)
                except (json.JSONDecodeError, TypeError):
                    flow_data = {}

                logger.info(
                    f"Flow response from {wa_id}: name={flow_name}, data={flow_data}"
                )

                # Remove internal/meta keys
                display_data = {
                    k: v
                    for k, v in flow_data.items()
                    if k not in ("flow_token", ) and v
                }

                # Save the raw flow submission as user message
                summary_lines = []
                for key, val in display_data.items():
                    label = key.replace("_", " ").replace("-", " ").title()
                    summary_lines.append(f"• *{label}:* {val}")

                user_summary = f"[Flow completed: {flow_name}]"
                if summary_lines:
                    user_summary += "\n" + "\n".join(summary_lines)
                await save_message(wa_id, "user", user_summary)

                # Build a nice acknowledgment echoing back what they submitted
                ack = f"✅ *Thank you for completing the form!*\n\n"
                if display_data:
                    ack += "📝 *Here's what you submitted:*\n"
                    for key, val in display_data.items():
                        label = key.replace("_", " ").replace("-", " ").title()
                        ack += f"  • *{label}:* {val}\n"
                    ack += "\n"
                ack += "⏳ We're processing your submission now, please hold on…"

                await send_text_message(wa_id, ack)
                await save_message(wa_id, "assistant", ack)

                # Simulate processing
                await asyncio.sleep(4)

                ref = f"DE-{wa_id[-4:]}-FLW{hash(response_json_str) % 10000:04d}"
                followup = (
                    f"🔔 *Your submission has been received!*\n\n"
                    f"Reference: *{ref}*\n\n"
                    f"📋 *What happens next:*\n"
                    f"1️⃣ Our team will review your details\n"
                    f"2️⃣ You'll get a confirmation within 24 hours\n"
                    f"3️⃣ If we need anything else, we'll reach out here\n\n"
                    f"You can continue chatting with us anytime! 💬")
                await send_text_message(wa_id, followup)
                await save_message(wa_id, "assistant", followup)
                return  # handled directly, skip AI agent

            else:
                # Unknown interactive type → pass to AI
                user_text = f"[Interactive reply: {reply_type}]"

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
