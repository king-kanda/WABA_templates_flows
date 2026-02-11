import httpx
import logging
import os
from app.config import get_settings

logger = logging.getLogger(__name__)


async def send_text_message(to: str, text: str):
    """Send a text message via WhatsApp Cloud API."""
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.meta_api_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {
            "body": text
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(settings.whatsapp_api_url,
                                         json=payload,
                                         headers=headers)
            response.raise_for_status()
            logger.info(f"Message sent to {to}")
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to send message to {to}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error sending message to {to}: {e}")
            raise


async def mark_as_read(message_id: str):
    """Mark a message as read."""
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.meta_api_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            await client.post(settings.whatsapp_api_url,
                              json=payload,
                              headers=headers)
        except Exception as e:
            logger.warning(f"Failed to mark message {message_id} as read: {e}")


async def download_media(media_id: str) -> bytes | None:
    """Download media from WhatsApp Cloud API."""
    settings = get_settings()
    headers = {"Authorization": f"Bearer {settings.meta_api_token}"}

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            # Step 1: Get media URL
            media_url_response = await client.get(
                f"{settings.whatsapp_media_url}/{media_id}", headers=headers)
            media_url_response.raise_for_status()
            media_url = media_url_response.json().get("url")

            if not media_url:
                logger.error(f"No URL found for media {media_id}")
                return None

            # Step 2: Download the media
            media_response = await client.get(media_url, headers=headers)
            media_response.raise_for_status()
            logger.info(
                f"Downloaded media {media_id} ({len(media_response.content)} bytes)"
            )
            return media_response.content

        except Exception as e:
            logger.error(f"Failed to download media {media_id}: {e}")
            return None


async def send_template_message(
    to: str,
    template_name: str,
    language_code: str = "en_US",
    flow_token: str = "unused",
    body_parameters: list[str] | None = None,
):
    """Send a template message via WhatsApp Cloud API."""
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.meta_api_token}",
        "Content-Type": "application/json",
    }

    components = []

    if body_parameters:
        components.append({
            "type":
            "body",
            "parameters": [{
                "type": "text",
                "text": p
            } for p in body_parameters],
        })

    components.append({
        "type":
        "button",
        "sub_type":
        "flow",
        "index":
        "0",
        "parameters": [{
            "type": "action",
            "action": {
                "flow_token": flow_token
            }
        }],
    })

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code
            },
        },
    }

    if components:
        payload["template"]["components"] = components

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            logger.info(f"Payload: {payload}")
            response = await client.post(settings.whatsapp_api_url,
                                         json=payload,
                                         headers=headers)
            response.raise_for_status()
            logger.info(f"Template '{template_name}' sent to {to}")
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to send template to {to}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error sending template to {to}: {e}")
            raise


async def save_media_file(media_data: bytes, wa_id: str, filename: str) -> str:
    """Save media data to the uploads directory."""
    settings = get_settings()
    user_dir = os.path.join(settings.uploads_dir, wa_id)
    os.makedirs(user_dir, exist_ok=True)
    file_path = os.path.join(user_dir, filename)
    with open(file_path, "wb") as f:
        f.write(media_data)
    logger.info(f"Saved media to {file_path}")
    return file_path


async def list_templates() -> list[dict]:
    """List all message templates from Meta WABA."""
    settings = get_settings()
    headers = {"Authorization": f"Bearer {settings.meta_api_token}"}
    url = f"https://graph.facebook.com/v21.0/{settings.meta_waba_business_account_id}/message_templates"

    all_templates = []
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            params = {"limit": 100}
            while url:
                response = await client.get(url,
                                            headers=headers,
                                            params=params)
                response.raise_for_status()
                data = response.json()
                all_templates.extend(data.get("data", []))
                # Pagination
                url = data.get("paging", {}).get("next")
                params = {}  # next URL already has params
            logger.info(f"Fetched {len(all_templates)} templates")
            return all_templates
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to list templates: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error listing templates: {e}")
            raise


async def create_template(
    name: str,
    category: str,
    language: str,
    header_text: str | None = None,
    body_text: str = "",
    footer_text: str | None = None,
    buttons: list[dict] | None = None,
) -> dict:
    """Create a new message template via Meta Graph API."""
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.meta_api_token}",
        "Content-Type": "application/json",
    }
    url = f"https://graph.facebook.com/v21.0/{settings.meta_waba_business_account_id}/message_templates"

    components = []

    if header_text:
        components.append({
            "type": "HEADER",
            "format": "TEXT",
            "text": header_text,
        })

    components.append({
        "type": "BODY",
        "text": body_text,
    })

    if footer_text:
        components.append({
            "type": "FOOTER",
            "text": footer_text,
        })

    if buttons:
        btn_component = {"type": "BUTTONS", "buttons": buttons}
        components.append(btn_component)

    payload = {
        "name": name,
        "category": category.upper(),
        "language": language,
        "components": components,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
            logger.info(f"Template '{name}' created: {result}")
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to create template: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error creating template: {e}")
            raise


async def send_interactive_list(to: str) -> dict:
    """Send an interactive list message with DriveEasy service options."""
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.meta_api_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {
                "type": "text",
                "text": "What would you like today? 🚗"
            },
            "body": {
                "text": "Choose one service to proceed:"
            },
            "footer": {
                "text": "DriveEasy Car Services"
            },
            "action": {
                "button":
                "Select Service",
                "sections": [{
                    "title":
                    "Service Options",
                    "rows": [
                        {
                            "id":
                            "full_financing",
                            "title":
                            "Full Financing 💰",
                            "description":
                            "Complete financing with easy installments.",
                        },
                        {
                            "id":
                            "top_up",
                            "title":
                            "Top Up 🔝",
                            "description":
                            "Add extra funds or upgrade your package.",
                        },
                        {
                            "id":
                            "vehicle_inspection",
                            "title":
                            "Vehicle Inspection 🔍",
                            "description":
                            "Professional check-up and certification.",
                        },
                        {
                            "id": "chauffer",
                            "title": "Chauffeur Service 👨‍✈️",
                            "description":
                            "Professional driver – relax and ride.",
                        },
                        {
                            "id": "rent_a_car",
                            "title": "Rent a Car 🚙",
                            "description":
                            "Short or long-term rental available.",
                        },
                    ],
                }],
            },
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(settings.whatsapp_api_url,
                                         json=payload,
                                         headers=headers)
            response.raise_for_status()
            logger.info(f"Interactive list sent to {to}")
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to send interactive list to {to}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error sending interactive list to {to}: {e}")
            raise


async def delete_template(template_name: str) -> dict:
    """Delete a message template by name."""
    settings = get_settings()
    headers = {"Authorization": f"Bearer {settings.meta_api_token}"}
    url = f"https://graph.facebook.com/v21.0/{settings.meta_waba_business_account_id}/message_templates"

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.delete(url,
                                           headers=headers,
                                           params={"name": template_name})
            response.raise_for_status()
            result = response.json()
            logger.info(f"Template '{template_name}' deleted")
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to delete template: {e.response.text}")
            raise
