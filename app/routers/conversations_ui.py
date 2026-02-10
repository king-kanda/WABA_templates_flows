"""Conversations UI - web dashboard to view all WhatsApp conversations."""

import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi import Form
from fastapi.responses import RedirectResponse
from app.services.conversation import get_all_conversations, get_conversation_messages
from app.services.whatsapp import send_template_message
from app.database import fetch_one

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ui", tags=["ui"])

CONVERSATIONS_LIST_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DriveEasy - Conversations</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f0f2f5;
            color: #111b21;
        }
        .header {
            background: #008069;
            color: white;
            padding: 16px 24px;
            display: flex;
            align-items: center;
            gap: 16px;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 1px 3px rgba(0,0,0,0.12);
        }
        .header h1 { font-size: 20px; font-weight: 600; }
        .header .subtitle { font-size: 13px; opacity: 0.85; margin-top: 2px; }
        .stats-bar {
            background: white;
            padding: 12px 24px;
            display: flex;
            gap: 32px;
            border-bottom: 1px solid #e9edef;
            flex-wrap: wrap;
        }
        .stat { text-align: center; }
        .stat-value { font-size: 24px; font-weight: 700; color: #008069; }
        .stat-label { font-size: 12px; color: #667781; margin-top: 2px; }
        .container { max-width: 900px; margin: 0 auto; padding: 16px; }
        .search-box {
            width: 100%;
            padding: 10px 16px;
            border: none;
            border-radius: 8px;
            background: white;
            font-size: 14px;
            margin-bottom: 16px;
            outline: none;
            box-shadow: 0 1px 2px rgba(0,0,0,0.08);
        }
        .search-box:focus { box-shadow: 0 0 0 2px #008069; }
        .conversation-list { display: flex; flex-direction: column; gap: 2px; }
        .conversation-item {
            background: white;
            padding: 14px 20px;
            display: flex;
            align-items: center;
            gap: 14px;
            cursor: pointer;
            transition: background 0.15s;
            border-radius: 8px;
            text-decoration: none;
            color: inherit;
        }
        .conversation-item:hover { background: #f5f6f6; }
        .avatar {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: #dfe5e7;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            color: #fff;
            font-weight: 600;
            flex-shrink: 0;
        }
        .avatar.a { background: #00a884; }
        .avatar.b { background: #53bdeb; }
        .avatar.c { background: #ff6b6b; }
        .avatar.d { background: #ffa726; }
        .avatar.e { background: #7c4dff; }
        .conv-info { flex: 1; min-width: 0; }
        .conv-name {
            font-weight: 600;
            font-size: 15px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .conv-preview {
            font-size: 13px;
            color: #667781;
            margin-top: 3px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .conv-meta {
            text-align: right;
            flex-shrink: 0;
        }
        .conv-time { font-size: 12px; color: #667781; }
        .conv-count {
            background: #25d366;
            color: white;
            font-size: 11px;
            font-weight: 600;
            padding: 2px 7px;
            border-radius: 10px;
            margin-top: 4px;
            display: inline-block;
        }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #667781;
        }
        .empty-state svg { width: 80px; height: 80px; margin-bottom: 16px; opacity: 0.4; }
        .empty-state h3 { font-size: 18px; margin-bottom: 8px; color: #111b21; }
        /* Template form */
        .template-section {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }
        .template-section h3 {
            font-size: 15px;
            font-weight: 600;
            margin-bottom: 12px;
            color: #008069;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .template-form {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .template-form .full-width { grid-column: 1 / -1; }
        .template-form label {
            font-size: 12px;
            color: #667781;
            display: block;
            margin-bottom: 4px;
            font-weight: 500;
        }
        .template-form input {
            width: 100%;
            padding: 9px 12px;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            font-size: 14px;
            outline: none;
            transition: border-color 0.15s;
        }
        .template-form input:focus { border-color: #008069; }
        .template-form button {
            background: #008069;
            color: white;
            border: none;
            padding: 10px 24px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.15s;
        }
        .template-form button:hover { background: #006e5a; }
        .template-form .hint {
            font-size: 11px;
            color: #9aa0a6;
            margin-top: 3px;
        }
        .alert {
            padding: 10px 16px;
            border-radius: 6px;
            margin-bottom: 12px;
            font-size: 13px;
        }
        .alert-success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .alert-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>DriveEasy Conversations</h1>
            <div class="subtitle">WhatsApp AI Agent Dashboard</div>
        </div>
    </div>
    <div class="stats-bar">
        <div class="stat">
            <div class="stat-value">{{ stats.total_conversations }}</div>
            <div class="stat-label">Conversations</div>
        </div>
        <div class="stat">
            <div class="stat-value">{{ stats.total_messages }}</div>
            <div class="stat-label">Total Messages</div>
        </div>
        <div class="stat">
            <div class="stat-value">{{ stats.total_bookings }}</div>
            <div class="stat-label">Bookings</div>
        </div>
        <div class="stat">
            <div class="stat-value">R{{ stats.total_revenue }}</div>
            <div class="stat-label">Revenue</div>
        </div>
    </div>
    <div class="container">
        {% if template_success %}
            <div class="alert alert-success">Template "demo" sent successfully to {{ template_success }}!</div>
        {% endif %}
        {% if template_error %}
            <div class="alert alert-error">{{ template_error }}</div>
        {% endif %}

        <div class="template-section">
            <h3>&#9993; Send Template Message (demo)</h3>
            <form class="template-form" method="POST" action="/ui/send-template">
                <div>
                    <label>Recipient Phone Number</label>
                    <input type="text" name="phone_number" placeholder="e.g. 27821234567" required>
                    <div class="hint">With country code, no + or spaces</div>
                </div>
                <div>
                    <label>Language</label>
                    <input type="text" name="language" value="en_US" placeholder="en_US">
                </div>
                <div>
                    <label>{{1}} - Body Variable 1</label>
                    <input type="text" name="var1" placeholder="e.g. #12345" required>
                </div>
                <div>
                    <label>{{2}} - Body Variable 2</label>
                    <input type="text" name="var2" placeholder="e.g. try a redelivery" required>
                </div>
                <div class="full-width" style="text-align: right;">
                    <button type="submit" id="sendBtn" onclick="this.disabled=true;this.textContent='Sending...';this.form.submit();">Send Template</button>
                </div>
            </form>
        </div>

        <input type="text" class="search-box" id="search" placeholder="Search conversations..." oninput="filterConversations()">
        <div class="conversation-list" id="convList">
            {% if conversations %}
                {% for conv in conversations %}
                <a href="/ui/conversations/{{ conv.wa_id }}" class="conversation-item" data-name="{{ conv.customer_name or conv.wa_id }}">
                    <div class="avatar {{ ['a','b','c','d','e'][loop.index0 % 5] }}">
                        {{ (conv.customer_name or conv.wa_id)[0:1].upper() }}
                    </div>
                    <div class="conv-info">
                        <div class="conv-name">{{ conv.customer_name or conv.wa_id }}</div>
                        <div class="conv-preview">{{ conv.last_user_message or 'No messages' }}</div>
                    </div>
                    <div class="conv-meta">
                        <div class="conv-time">{{ conv.last_message_at[:16] if conv.last_message_at else '' }}</div>
                        <div class="conv-count">{{ conv.message_count }}</div>
                    </div>
                </a>
                {% endfor %}
            {% else %}
                <div class="empty-state">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                    <h3>No conversations yet</h3>
                    <p>Conversations will appear here when customers message the WhatsApp bot.</p>
                </div>
            {% endif %}
        </div>
    </div>
    <script>
        function filterConversations() {
            const q = document.getElementById('search').value.toLowerCase();
            document.querySelectorAll('.conversation-item').forEach(item => {
                const name = item.dataset.name.toLowerCase();
                item.style.display = name.includes(q) ? '' : 'none';
            });
        }
    </script>
</body>
</html>
"""

CONVERSATION_DETAIL_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ customer_name or wa_id }} - DriveEasy</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #efeae2;
            color: #111b21;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .chat-bg {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: #efeae2;
            opacity: 0.06;
            background-image: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23000' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
            z-index: 0;
        }
        .header {
            background: #008069;
            color: white;
            padding: 12px 24px;
            display: flex;
            align-items: center;
            gap: 14px;
            z-index: 10;
            box-shadow: 0 1px 3px rgba(0,0,0,0.12);
        }
        .back-btn {
            color: white;
            text-decoration: none;
            font-size: 22px;
            padding: 4px 8px;
            border-radius: 50%;
            transition: background 0.15s;
        }
        .back-btn:hover { background: rgba(255,255,255,0.1); }
        .header-info h2 { font-size: 16px; font-weight: 600; }
        .header-info .wa-id { font-size: 12px; opacity: 0.8; }
        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 16px 24px;
            max-width: 900px;
            margin: 0 auto;
            width: 100%;
            z-index: 1;
            position: relative;
        }
        .message {
            max-width: 65%;
            margin-bottom: 4px;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 14px;
            line-height: 1.45;
            position: relative;
            word-wrap: break-word;
            box-shadow: 0 1px 1px rgba(0,0,0,0.06);
        }
        .message.user {
            background: #d9fdd3;
            margin-left: auto;
            border-top-right-radius: 0;
        }
        .message.assistant {
            background: white;
            margin-right: auto;
            border-top-left-radius: 0;
        }
        .message.tool {
            background: #fff3cd;
            margin-right: auto;
            border-top-left-radius: 0;
            font-family: 'SF Mono', Monaco, Consolas, monospace;
            font-size: 12px;
            max-width: 80%;
            border-left: 3px solid #ffc107;
        }
        .message.system {
            background: #e3f2fd;
            margin: 8px auto;
            max-width: 80%;
            text-align: center;
            font-size: 12px;
            border-radius: 8px;
        }
        .msg-time {
            font-size: 11px;
            color: #667781;
            text-align: right;
            margin-top: 4px;
        }
        .msg-role {
            font-size: 10px;
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.5px;
            margin-bottom: 3px;
            opacity: 0.6;
        }
        .tool-label {
            display: inline-block;
            background: #ffc107;
            color: #333;
            font-size: 10px;
            font-weight: 600;
            padding: 1px 6px;
            border-radius: 3px;
            margin-bottom: 4px;
        }
        .date-separator {
            text-align: center;
            margin: 16px 0;
        }
        .date-separator span {
            background: #e1f3fb;
            color: #54656f;
            font-size: 12px;
            padding: 5px 12px;
            border-radius: 8px;
            box-shadow: 0 1px 1px rgba(0,0,0,0.06);
        }
        .tool-calls-info {
            font-size: 11px;
            color: #667781;
            font-style: italic;
            margin-top: 4px;
        }
        pre {
            white-space: pre-wrap;
            word-wrap: break-word;
            margin: 0;
        }
        .auto-refresh {
            position: fixed;
            bottom: 16px;
            right: 16px;
            z-index: 100;
            background: #008069;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 13px;
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }
        .auto-refresh:hover { background: #006e5a; }
    </style>
</head>
<body>
    <div class="chat-bg"></div>
    <div class="header">
        <a href="/ui" class="back-btn">&larr;</a>
        <div class="header-info">
            <h2>{{ customer_name or "Unknown Customer" }}</h2>
            <div class="wa-id">{{ wa_id }} &middot; {{ messages|length }} messages</div>
        </div>
    </div>
    <div class="chat-container" id="chatContainer">
        {% set prev_date = namespace(val='') %}
        {% for msg in messages %}
            {% set msg_date = msg.created_at[:10] if msg.created_at else '' %}
            {% if msg_date != prev_date.val %}
                <div class="date-separator"><span>{{ msg_date }}</span></div>
                {% set prev_date.val = msg_date %}
            {% endif %}

            {% if msg.role == 'tool' %}
                <div class="message tool">
                    <span class="tool-label">TOOL RESPONSE{% if msg.tool_call_id %} ({{ msg.tool_call_id[:12] }}){% endif %}</span>
                    <pre>{{ msg.content[:500] if msg.content else 'No content' }}{% if msg.content and msg.content|length > 500 %}...{% endif %}</pre>
                    <div class="msg-time">{{ msg.created_at[11:16] if msg.created_at else '' }}</div>
                </div>
            {% elif msg.role == 'assistant' %}
                <div class="message assistant">
                    <div class="msg-role">AI Agent</div>
                    {% if msg.content %}{{ msg.content }}{% endif %}
                    {% if msg.tool_calls %}
                        <div class="tool-calls-info">Called tools: {{ msg.tool_calls }}</div>
                    {% endif %}
                    <div class="msg-time">{{ msg.created_at[11:16] if msg.created_at else '' }}</div>
                </div>
            {% elif msg.role == 'user' %}
                <div class="message user">
                    <div class="msg-role">Customer</div>
                    {{ msg.content or '[No text]' }}
                    <div class="msg-time">{{ msg.created_at[11:16] if msg.created_at else '' }}</div>
                </div>
            {% else %}
                <div class="message system">{{ msg.content or msg.role }}</div>
            {% endif %}
        {% endfor %}
    </div>
    <button class="auto-refresh" onclick="location.reload()">Refresh</button>
    <script>
        const container = document.getElementById('chatContainer');
        container.scrollTop = container.scrollHeight;
        // Auto-refresh every 10 seconds
        setInterval(() => location.reload(), 10000);
    </script>
</body>
</html>
"""


@router.get("", response_class=HTMLResponse)
async def conversations_list(
    request: Request,
    template_success: str | None = None,
    template_error: str | None = None,
):
    """Show all conversations."""
    conversations = await get_all_conversations()

    # Get stats
    from app.database import fetch_one
    total_messages = await fetch_one(
        "SELECT COUNT(*) as count FROM conversations")
    total_bookings = await fetch_one("SELECT COUNT(*) as count FROM bookings")
    revenue = await fetch_one(
        "SELECT COALESCE(SUM(total_price), 0) as total FROM bookings WHERE status != 'cancelled'"
    )

    stats = {
        "total_conversations": len(conversations),
        "total_messages": total_messages["count"] if total_messages else 0,
        "total_bookings": total_bookings["count"] if total_bookings else 0,
        "total_revenue": f"{revenue['total']:,.0f}" if revenue else "0",
    }

    # Simple template rendering (no Jinja2 dependency needed for basic cases)
    from jinja2 import Template
    template = Template(CONVERSATIONS_LIST_HTML)
    html = template.render(
        conversations=conversations,
        stats=stats,
        template_success=template_success,
        template_error=template_error,
    )
    return HTMLResponse(content=html)


@router.post("/send-template")
async def send_template(
        phone_number: str = Form(...),
        language: str = Form("en_US"),
        var1: str = Form(...),
        var2: str = Form(...),
):
    """Send the 'demo' template message with two body variables."""
    try:
        await send_template_message(
            to=phone_number,
            template_name="demo_template",
            language_code=language,
            body_parameters=[var1, var2],
        )
        return RedirectResponse(
            url=f"/ui?template_success={phone_number}",
            status_code=303,
        )
    except Exception as e:
        error_msg = str(e)[:200]
        return RedirectResponse(
            url=f"/ui?template_error={error_msg}",
            status_code=303,
        )


@router.get("/conversations/{wa_id}", response_class=HTMLResponse)
async def conversation_detail(wa_id: str):
    """Show a specific conversation thread."""
    messages = await get_conversation_messages(wa_id, limit=500)

    # Get customer name
    customer = await fetch_one("SELECT name FROM customers WHERE wa_id = ?",
                               (wa_id, ))
    customer_name = customer["name"] if customer and customer.get(
        "name") else None

    from jinja2 import Template
    template = Template(CONVERSATION_DETAIL_HTML)
    html = template.render(
        wa_id=wa_id,
        customer_name=customer_name,
        messages=messages,
    )
    return HTMLResponse(content=html)
