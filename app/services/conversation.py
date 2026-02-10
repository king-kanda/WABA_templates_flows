import logging
import json
from app.database import fetch_all, execute

logger = logging.getLogger(__name__)

MAX_HISTORY = 20


async def save_message(wa_id: str,
                       role: str,
                       content: str | None = None,
                       tool_call_id: str | None = None,
                       tool_calls: list | None = None):
    """Save a conversation message to the database."""
    tool_calls_json = json.dumps(tool_calls) if tool_calls else None
    await execute(
        """INSERT INTO conversations (wa_id, role, content, tool_call_id, tool_calls)
           VALUES (?, ?, ?, ?, ?)""",
        (wa_id, role, content, tool_call_id, tool_calls_json),
    )


async def load_history(wa_id: str) -> list[dict]:
    """Load the last N messages for a WhatsApp ID, formatted for Groq."""
    rows = await fetch_all(
        """SELECT role, content, tool_call_id, tool_calls
           FROM conversations
           WHERE wa_id = ?
           ORDER BY created_at DESC
           LIMIT ?""",
        (wa_id, MAX_HISTORY),
    )
    # Reverse to chronological order
    rows.reverse()

    messages = []
    for row in rows:
        msg = {"role": row["role"]}
        if row["content"]:
            msg["content"] = row["content"]
        if row["tool_call_id"]:
            msg["tool_call_id"] = row["tool_call_id"]
        if row["tool_calls"]:
            msg["tool_calls"] = json.loads(row["tool_calls"])
            if not row["content"]:
                msg["content"] = None
        messages.append(msg)

    return messages


async def get_all_conversations() -> list[dict]:
    """Get all unique conversation threads with last message preview."""
    return await fetch_all("""
        SELECT
            c.wa_id,
            cu.name as customer_name,
            COUNT(*) as message_count,
            MAX(c.created_at) as last_message_at,
            (SELECT content FROM conversations c2
             WHERE c2.wa_id = c.wa_id AND c2.role = 'user'
             ORDER BY c2.created_at DESC LIMIT 1) as last_user_message
        FROM conversations c
        LEFT JOIN customers cu ON cu.wa_id = c.wa_id
        GROUP BY c.wa_id
        ORDER BY MAX(c.created_at) DESC
    """)


async def get_conversation_messages(wa_id: str,
                                    limit: int = 100) -> list[dict]:
    """Get full conversation messages for a specific WhatsApp ID."""
    return await fetch_all(
        """SELECT id, wa_id, role, content, tool_call_id, tool_calls, created_at
           FROM conversations
           WHERE wa_id = ?
           ORDER BY created_at ASC
           LIMIT ?""",
        (wa_id, limit),
    )
