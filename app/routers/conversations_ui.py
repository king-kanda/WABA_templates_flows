"""HTMX-powered dashboard with tabs: Conversations, Templates, Create Template, Send Template."""

import logging
import json
from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse
from app.services.conversation import get_all_conversations, get_conversation_messages
from app.services.whatsapp import send_template_message, list_templates, create_template, delete_template
from app.database import fetch_one

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ui", tags=["ui"])

# ──────────────────────────── SHELL (tabs + layout) ────────────────────────────

SHELL_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DriveEasy — WABA Dashboard</title>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f0f2f5;
            color: #111b21;
        }
        /* ── header ── */
        .header {
            background: #008069;
            color: white;
            padding: 14px 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,.12);
            position: sticky; top: 0; z-index: 100;
        }
        .header h1 { font-size: 18px; font-weight: 700; }
        .header .sub { font-size: 12px; opacity: .8; margin-top: 2px; }

        /* ── tabs ── */
        .tab-bar {
            display: flex;
            background: white;
            border-bottom: 2px solid #e9edef;
            position: sticky; top: 52px; z-index: 99;
        }
        .tab-btn {
            flex: 1;
            padding: 12px 0;
            text-align: center;
            font-size: 13px;
            font-weight: 600;
            color: #667781;
            cursor: pointer;
            border: none;
            background: none;
            border-bottom: 3px solid transparent;
            transition: all .15s;
        }
        .tab-btn:hover { color: #008069; background: #f5f6f6; }
        .tab-btn.active { color: #008069; border-bottom-color: #008069; }

        /* ── content ── */
        .tab-content {
            max-width: 960px;
            margin: 0 auto;
            padding: 20px 16px;
            min-height: 60vh;
        }

        /* ── shared card ── */
        .card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,.06);
        }
        .card h3 {
            font-size: 15px; font-weight: 600; margin-bottom: 14px; color: #008069;
        }

        /* ── stats row ── */
        .stats { display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 16px; }
        .stat { text-align: center; }
        .stat-val { font-size: 22px; font-weight: 700; color: #008069; }
        .stat-lbl { font-size: 11px; color: #667781; margin-top: 2px; }

        /* ── form grid ── */
        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }
        .form-grid .full { grid-column: 1 / -1; }
        .form-grid label {
            display: block; font-size: 12px; font-weight: 500; color: #667781; margin-bottom: 4px;
        }
        .form-grid input,
        .form-grid select,
        .form-grid textarea {
            width: 100%; padding: 9px 12px; border: 1px solid #e0e0e0;
            border-radius: 6px; font-size: 14px; outline: none;
            font-family: inherit; transition: border-color .15s;
        }
        .form-grid input:focus,
        .form-grid select:focus,
        .form-grid textarea:focus { border-color: #008069; }
        .form-grid textarea { resize: vertical; min-height: 80px; }
        .hint { font-size: 11px; color: #9aa0a6; margin-top: 3px; }

        /* ── buttons ── */
        .btn {
            display: inline-block; padding: 10px 24px; border: none; border-radius: 6px;
            font-size: 14px; font-weight: 600; cursor: pointer; transition: background .15s;
        }
        .btn-primary { background: #008069; color: white; }
        .btn-primary:hover { background: #006e5a; }
        .btn-danger { background: #dc3545; color: white; }
        .btn-danger:hover { background: #c82333; }
        .btn-sm { padding: 5px 12px; font-size: 12px; }
        .btn:disabled { opacity: .6; cursor: not-allowed; }

        /* ── alerts ── */
        .alert {
            padding: 10px 16px; border-radius: 6px; margin-bottom: 14px; font-size: 13px;
        }
        .alert-ok { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .alert-err { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }

        /* ── search ── */
        .search-box {
            width: 100%; padding: 10px 16px; border: none; border-radius: 8px;
            background: white; font-size: 14px; margin-bottom: 14px; outline: none;
            box-shadow: 0 1px 2px rgba(0,0,0,.08);
        }
        .search-box:focus { box-shadow: 0 0 0 2px #008069; }

        /* ── conversation list ── */
        .conv-item {
            background: white; padding: 13px 18px; display: flex; align-items: center;
            gap: 14px; cursor: pointer; border-radius: 8px; text-decoration: none;
            color: inherit; transition: background .15s; margin-bottom: 2px;
        }
        .conv-item:hover { background: #f5f6f6; }
        .avatar {
            width: 44px; height: 44px; border-radius: 50%; display: flex;
            align-items: center; justify-content: center; font-size: 18px;
            color: #fff; font-weight: 600; flex-shrink: 0;
        }
        .av-a{background:#00a884}.av-b{background:#53bdeb}.av-c{background:#ff6b6b}.av-d{background:#ffa726}.av-e{background:#7c4dff}
        .conv-info { flex: 1; min-width: 0; }
        .conv-name { font-weight: 600; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .conv-preview { font-size: 12px; color: #667781; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .conv-meta { text-align: right; flex-shrink: 0; }
        .conv-time { font-size: 11px; color: #667781; }
        .badge { background: #25d366; color: white; font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 10px; margin-top: 4px; display: inline-block; }

        /* ── template table ── */
        .tpl-table { width: 100%; border-collapse: collapse; font-size: 13px; }
        .tpl-table th { text-align: left; font-size: 11px; text-transform: uppercase; color: #667781; padding: 8px 10px; border-bottom: 2px solid #e9edef; }
        .tpl-table td { padding: 10px; border-bottom: 1px solid #f0f2f5; vertical-align: top; }
        .tpl-table tr:hover td { background: #f9fafb; }
        .status-badge {
            display: inline-block; padding: 2px 8px; border-radius: 10px;
            font-size: 11px; font-weight: 600; text-transform: uppercase;
        }
        .st-approved { background: #d4edda; color: #155724; }
        .st-rejected { background: #f8d7da; color: #721c24; }
        .st-pending { background: #fff3cd; color: #856404; }
        .st-other { background: #e9edef; color: #667781; }

        /* ── chat view ── */
        .chat-header {
            background: #008069; color: white; padding: 12px 20px;
            display: flex; align-items: center; gap: 12px; border-radius: 10px 10px 0 0;
        }
        .chat-header .back { color: white; text-decoration: none; font-size: 20px; cursor: pointer; }
        .chat-body {
            background: #efeae2; padding: 16px 20px; max-height: 60vh;
            overflow-y: auto; border-radius: 0 0 10px 10px;
        }
        .msg {
            max-width: 70%; margin-bottom: 4px; padding: 8px 12px;
            border-radius: 8px; font-size: 13px; line-height: 1.45;
            word-wrap: break-word; box-shadow: 0 1px 1px rgba(0,0,0,.06);
        }
        .msg-user { background: #d9fdd3; margin-left: auto; border-top-right-radius: 0; }
        .msg-ai { background: white; margin-right: auto; border-top-left-radius: 0; }
        .msg-tool {
            background: #fff3cd; margin-right: auto; border-top-left-radius: 0;
            font-family: monospace; font-size: 11px; max-width: 85%;
            border-left: 3px solid #ffc107;
        }
        .msg-role { font-size: 10px; text-transform: uppercase; font-weight: 600; opacity: .55; margin-bottom: 2px; letter-spacing: .3px; }
        .msg-time { font-size: 10px; color: #667781; text-align: right; margin-top: 3px; }
        .date-sep { text-align: center; margin: 14px 0; }
        .date-sep span { background: #e1f3fb; color: #54656f; font-size: 11px; padding: 4px 12px; border-radius: 8px; }

        /* ── spinner ── */
        .htmx-indicator { display: none; }
        .htmx-request .htmx-indicator { display: inline-block; }
        .spinner { display: inline-block; width: 18px; height: 18px; border: 2px solid #ddd; border-top-color: #008069; border-radius: 50%; animation: spin .6s linear infinite; vertical-align: middle; margin-left: 6px; }
        @keyframes spin { to { transform: rotate(360deg); } }

        /* empty */
        .empty { text-align: center; padding: 50px 20px; color: #667781; }
        .empty h4 { color: #111b21; margin-bottom: 6px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>DriveEasy &mdash; WABA Dashboard</h1>
        <div class="sub">WhatsApp Business API &middot; Templates &middot; Flows</div>
    </div>

    <div class="tab-bar" id="tabBar">
        <button class="tab-btn active" data-tab="conversations"
                hx-get="/ui/tab/conversations" hx-target="#content" hx-swap="innerHTML"
                onclick="setActive(this)">
            Conversations
        </button>
        <button class="tab-btn" data-tab="templates"
                hx-get="/ui/tab/templates" hx-target="#content" hx-swap="innerHTML"
                onclick="setActive(this)">
            Templates
        </button>
        <button class="tab-btn" data-tab="create"
                hx-get="/ui/tab/create-template" hx-target="#content" hx-swap="innerHTML"
                onclick="setActive(this)">
            Create Template
        </button>
        <button class="tab-btn" data-tab="send"
                hx-get="/ui/tab/send-template" hx-target="#content" hx-swap="innerHTML"
                onclick="setActive(this)">
            Send Template
        </button>
    </div>

    <div class="tab-content" id="content"
         hx-get="/ui/tab/conversations" hx-trigger="load" hx-swap="innerHTML">
        <div style="text-align:center;padding:40px"><span class="spinner"></span> Loading...</div>
    </div>

    <script>
        function setActive(el) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            el.classList.add('active');
        }
        function filterConvs() {
            const q = document.getElementById('convSearch').value.toLowerCase();
            document.querySelectorAll('.conv-item').forEach(i => {
                i.style.display = (i.dataset.name||'').toLowerCase().includes(q) ? '' : 'none';
            });
        }
    </script>
</body>
</html>
"""

# ──────────────────────────── TAB: CONVERSATIONS ────────────────────────────

CONVERSATIONS_TAB = """
<div class="stats">
    <div class="stat"><div class="stat-val">{{ stats.total_conversations }}</div><div class="stat-lbl">Conversations</div></div>
    <div class="stat"><div class="stat-val">{{ stats.total_messages }}</div><div class="stat-lbl">Messages</div></div>
    <div class="stat"><div class="stat-val">{{ stats.total_bookings }}</div><div class="stat-lbl">Bookings</div></div>
    <div class="stat"><div class="stat-val">R{{ stats.total_revenue }}</div><div class="stat-lbl">Revenue</div></div>
</div>

<input type="text" class="search-box" id="convSearch" placeholder="Search conversations..." oninput="filterConvs()">

{% if conversations %}
    {% for c in conversations %}
    <div class="conv-item" data-name="{{ c.customer_name or c.wa_id }}"
         hx-get="/ui/tab/chat/{{ c.wa_id }}" hx-target="#content" hx-swap="innerHTML">
        <div class="avatar av-{{ ['a','b','c','d','e'][loop.index0 % 5] }}">
            {{ (c.customer_name or c.wa_id)[0:1].upper() }}
        </div>
        <div class="conv-info">
            <div class="conv-name">{{ c.customer_name or c.wa_id }}</div>
            <div class="conv-preview">{{ c.last_user_message or 'No messages yet' }}</div>
        </div>
        <div class="conv-meta">
            <div class="conv-time">{{ c.last_message_at[:16] if c.last_message_at else '' }}</div>
            <div class="badge">{{ c.message_count }}</div>
        </div>
    </div>
    {% endfor %}
{% else %}
    <div class="empty">
        <h4>No conversations yet</h4>
        <p>Conversations appear when customers message the WhatsApp bot.</p>
    </div>
{% endif %}
"""

# ──────────────────────────── TAB: CHAT DETAIL ────────────────────────────

CHAT_DETAIL_TAB = """
<div class="card" style="padding:0; overflow:hidden;">
    <div class="chat-header">
        <span class="back" hx-get="/ui/tab/conversations" hx-target="#content" hx-swap="innerHTML"
              onclick="document.querySelector('[data-tab=conversations]').classList.add('active');
                       document.querySelectorAll('.tab-btn:not([data-tab=conversations])').forEach(b=>b.classList.remove('active'));">&larr;</span>
        <div>
            <div style="font-weight:600">{{ customer_name or 'Unknown' }}</div>
            <div style="font-size:12px;opacity:.8">{{ wa_id }} &middot; {{ messages|length }} messages</div>
        </div>
        <div style="margin-left:auto">
            <button class="btn btn-sm" style="background:rgba(255,255,255,.2);color:white"
                    hx-get="/ui/tab/chat/{{ wa_id }}" hx-target="#content" hx-swap="innerHTML">
                Refresh
            </button>
        </div>
    </div>
    <div class="chat-body" id="chatBody">
        {% set prev_date = namespace(val='') %}
        {% for m in messages %}
            {% set md = m.created_at[:10] if m.created_at else '' %}
            {% if md != prev_date.val %}
                <div class="date-sep"><span>{{ md }}</span></div>
                {% set prev_date.val = md %}
            {% endif %}

            {% if m.role == 'tool' %}
                <div class="msg msg-tool">
                    <span style="background:#ffc107;color:#333;font-size:10px;font-weight:600;padding:1px 6px;border-radius:3px">TOOL{% if m.tool_call_id %} {{ m.tool_call_id[:10] }}{% endif %}</span>
                    <pre style="white-space:pre-wrap;margin:4px 0 0">{{ m.content[:400] if m.content else '' }}{% if m.content and m.content|length > 400 %}...{% endif %}</pre>
                    <div class="msg-time">{{ m.created_at[11:16] if m.created_at else '' }}</div>
                </div>
            {% elif m.role == 'assistant' %}
                <div class="msg msg-ai">
                    <div class="msg-role">AI Agent</div>
                    {{ m.content or '' }}
                    {% if m.tool_calls %}<div style="font-size:11px;color:#667781;margin-top:4px;font-style:italic">Tools: {{ m.tool_calls }}</div>{% endif %}
                    <div class="msg-time">{{ m.created_at[11:16] if m.created_at else '' }}</div>
                </div>
            {% elif m.role == 'user' %}
                <div class="msg msg-user">
                    <div class="msg-role">Customer</div>
                    {{ m.content or '[no text]' }}
                    <div class="msg-time">{{ m.created_at[11:16] if m.created_at else '' }}</div>
                </div>
            {% endif %}
        {% endfor %}
    </div>
</div>
<script>
    (function(){ var el=document.getElementById('chatBody'); if(el) el.scrollTop=el.scrollHeight; })();
</script>
"""

# ──────────────────────────── TAB: TEMPLATES LIST ────────────────────────────

TEMPLATES_TAB = """
{% if error %}
    <div class="alert alert-err">{{ error }}</div>
{% endif %}

<div class="card">
    <h3>Message Templates ({{ templates|length }})</h3>
    {% if templates %}
    <div style="overflow-x:auto">
        <table class="tpl-table">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Category</th>
                    <th>Language</th>
                    <th>Status</th>
                    <th>Body</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                {% for t in templates %}
                <tr>
                    <td style="font-weight:600">{{ t.name }}</td>
                    <td>{{ t.category or '—' }}</td>
                    <td>{{ t.language or '—' }}</td>
                    <td>
                        {% set st = (t.status or '')|lower %}
                        <span class="status-badge {% if st=='approved' %}st-approved{% elif st=='rejected' %}st-rejected{% elif st=='pending' %}st-pending{% else %}st-other{% endif %}">
                            {{ t.status or 'UNKNOWN' }}
                        </span>
                    </td>
                    <td style="max-width:280px;font-size:12px;color:#555">
                        {{ t.body_text or '—' }}
                    </td>
                    <td>
                        <button class="btn btn-danger btn-sm"
                                hx-delete="/ui/api/templates/{{ t.name }}"
                                hx-target="#content" hx-swap="innerHTML"
                                hx-confirm="Delete template '{{ t.name }}'? This cannot be undone.">
                            Delete
                        </button>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
        <div class="empty"><h4>No templates found</h4><p>Create one using the "Create Template" tab.</p></div>
    {% endif %}
</div>
"""

# ──────────────────────────── TAB: CREATE TEMPLATE ────────────────────────────

CREATE_TEMPLATE_TAB = """
<div class="card">
    <h3>Create a New WhatsApp Template</h3>
    <div id="createResult"></div>
    <form class="form-grid"
          hx-post="/ui/api/templates" hx-target="#createResult" hx-swap="innerHTML"
          hx-disabled-elt="button[type=submit]">
        <div>
            <label>Template Name</label>
            <input type="text" name="name" placeholder="e.g. order_update" required pattern="[a-z0-9_]+"
                   title="Lowercase letters, numbers, and underscores only">
            <div class="hint">Lowercase, no spaces. e.g. booking_confirm</div>
        </div>
        <div>
            <label>Category</label>
            <select name="category" required>
                <option value="MARKETING">Marketing</option>
                <option value="UTILITY" selected>Utility</option>
                <option value="AUTHENTICATION">Authentication</option>
            </select>
        </div>
        <div>
            <label>Language</label>
            <select name="language" required>
                <option value="en_US" selected>English (US)</option>
                <option value="en_GB">English (UK)</option>
                <option value="af">Afrikaans</option>
                <option value="zu">Zulu</option>
                <option value="fr">French</option>
                <option value="es">Spanish</option>
                <option value="pt_BR">Portuguese (BR)</option>
            </select>
        </div>
        <div>
            <label>Header (optional)</label>
            <input type="text" name="header_text" placeholder="e.g. Booking Confirmation">
        </div>
        <div class="full">
            <label>Body Text</label>
            <textarea name="body_text" required
                      placeholder="Your booking {{1}} is confirmed for {{2}}.&#10;&#10;Use {{1}}, {{2}}, etc. for variables."></textarea>
            <div class="hint">Use &#123;&#123;1&#125;&#125;, &#123;&#123;2&#125;&#125; for dynamic variables</div>
        </div>
        <div class="full">
            <label>Footer (optional)</label>
            <input type="text" name="footer_text" placeholder="e.g. DriveEasy Car Rentals">
        </div>
        <div class="full" style="text-align:right; margin-top:8px;">
            <button type="submit" class="btn btn-primary">
                Create Template <span class="htmx-indicator spinner"></span>
            </button>
        </div>
    </form>
</div>
"""

# ──────────────────────────── TAB: SEND TEMPLATE ────────────────────────────

SEND_TEMPLATE_TAB = """
<div class="card">
    <h3>Send a Template Message</h3>
    <div id="sendResult"></div>
    <form class="form-grid"
          hx-post="/ui/api/send-template" hx-target="#sendResult" hx-swap="innerHTML"
          hx-disabled-elt="button[type=submit]">
        <div>
            <label>Template Name</label>
            <input type="text" name="template_name" placeholder="e.g. demo" value="demo" required>
        </div>
        <div>
            <label>Recipient Phone Number</label>
            <input type="text" name="phone_number" placeholder="e.g. 27821234567" required>
            <div class="hint">With country code, no + or spaces</div>
        </div>
        <div>
            <label>Language</label>
            <input type="text" name="language" value="en_US">
        </div>
        <div>
            <label>Body Variables (comma-separated)</label>
            <input type="text" name="variables" placeholder="e.g. #12345, try a redelivery">
            <div class="hint">Leave empty if template has no variables</div>
        </div>
        <div class="full" style="text-align:right; margin-top:8px;">
            <button type="submit" class="btn btn-primary">
                Send Template <span class="htmx-indicator spinner"></span>
            </button>
        </div>
    </form>
</div>
"""

# ════════════════════════════ ROUTES ════════════════════════════


@router.get("", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard shell — everything else loads via HTMX."""
    return HTMLResponse(content=SHELL_HTML)


# ──── tab partials ────


@router.get("/tab/conversations", response_class=HTMLResponse)
async def tab_conversations():
    conversations = await get_all_conversations()

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

    from jinja2 import Template
    t = Template(CONVERSATIONS_TAB)
    return HTMLResponse(
        content=t.render(conversations=conversations, stats=stats))


@router.get("/tab/chat/{wa_id}", response_class=HTMLResponse)
async def tab_chat(wa_id: str):
    messages = await get_conversation_messages(wa_id, limit=500)
    customer = await fetch_one("SELECT name FROM customers WHERE wa_id = ?",
                               (wa_id, ))
    customer_name = customer["name"] if customer and customer.get(
        "name") else None

    from jinja2 import Template
    t = Template(CHAT_DETAIL_TAB)
    return HTMLResponse(content=t.render(
        wa_id=wa_id, customer_name=customer_name, messages=messages))


@router.get("/tab/templates", response_class=HTMLResponse)
async def tab_templates():
    error = None
    templates_data = []
    try:
        raw = await list_templates()
        for tpl in raw:
            body_text = ""
            for comp in tpl.get("components", []):
                if comp.get("type") == "BODY":
                    body_text = comp.get("text", "")
                    break
            templates_data.append({
                "name": tpl.get("name", ""),
                "category": tpl.get("category", ""),
                "language": tpl.get("language", ""),
                "status": tpl.get("status", ""),
                "body_text": body_text[:200],
            })
    except Exception as e:
        error = str(e)[:300]

    from jinja2 import Template
    t = Template(TEMPLATES_TAB)
    return HTMLResponse(
        content=t.render(templates=templates_data, error=error))


@router.get("/tab/create-template", response_class=HTMLResponse)
async def tab_create_template():
    return HTMLResponse(content=CREATE_TEMPLATE_TAB)


@router.get("/tab/send-template", response_class=HTMLResponse)
async def tab_send_template():
    return HTMLResponse(content=SEND_TEMPLATE_TAB)


# ──── API actions (return HTML snippets for htmx) ────


@router.post("/api/templates", response_class=HTMLResponse)
async def api_create_template(
        name: str = Form(...),
        category: str = Form("UTILITY"),
        language: str = Form("en_US"),
        header_text: str = Form(""),
        body_text: str = Form(...),
        footer_text: str = Form(""),
):
    try:
        result = await create_template(
            name=name,
            category=category,
            language=language,
            header_text=header_text or None,
            body_text=body_text,
            footer_text=footer_text or None,
        )
        tid = result.get("id", "")
        return HTMLResponse(
            f'<div class="alert alert-ok">Template <b>{name}</b> created successfully! ID: {tid}. '
            f'It will be reviewed by Meta before becoming active.</div>')
    except Exception as e:
        return HTMLResponse(
            f'<div class="alert alert-err">Failed to create template: {e}</div>'
        )


@router.post("/api/send-template", response_class=HTMLResponse)
async def api_send_template(
        template_name: str = Form(...),
        phone_number: str = Form(...),
        language: str = Form("en_US"),
        variables: str = Form(""),
):
    try:
        body_params = [v.strip() for v in variables.split(",")
                       if v.strip()] if variables.strip() else None
        await send_template_message(
            to=phone_number,
            template_name=template_name,
            language_code=language,
            body_parameters=body_params,
        )
        return HTMLResponse(
            f'<div class="alert alert-ok">Template <b>{template_name}</b> sent to {phone_number} successfully!</div>'
        )
    except Exception as e:
        return HTMLResponse(
            f'<div class="alert alert-err">Failed to send: {e}</div>')


@router.delete("/api/templates/{template_name}", response_class=HTMLResponse)
async def api_delete_template(template_name: str):
    try:
        await delete_template(template_name)
    except Exception as e:
        return HTMLResponse(
            f'<div class="alert alert-err">Delete failed: {e}</div>')

    # Re-render the templates tab
    return await tab_templates()
