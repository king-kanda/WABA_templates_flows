"""HTMX + Tailwind CSS dashboard — Conversations, Templates, Create Template, Send Template."""

import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from app.services.conversation import get_all_conversations, get_conversation_messages
from app.services.whatsapp import send_template_message, list_templates, create_template, delete_template, send_interactive_list, _has_flow_button
from app.database import fetch_one

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ui", tags=["ui"])

# ──────────────────────────── SHELL ────────────────────────────

SHELL_HTML = """
<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DriveEasy — WABA Dashboard</title>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        wa: { DEFAULT: '#008069', light: '#00a884', dark: '#006e5a', bg: '#efeae2', bubble: '#d9fdd3' }
                    }
                }
            }
        }
    </script>
    <style>
        .htmx-indicator { display: none; }
        .htmx-request .htmx-indicator { display: inline-block; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .spinner { animation: spin .6s linear infinite; }
        /* custom scrollbar */
        .chat-scroll::-webkit-scrollbar { width: 6px; }
        .chat-scroll::-webkit-scrollbar-thumb { background: #c5c5c5; border-radius: 3px; }
    </style>
</head>
<body class="bg-gray-100 font-sans text-gray-900 min-h-full">

    <!-- Header -->
    <header class="bg-wa text-white px-6 py-3.5 sticky top-0 z-50 shadow-md">
        <h1 class="text-lg font-bold tracking-tight">DriveEasy &mdash; WABA Dashboard</h1>
        <p class="text-xs text-white/70 mt-0.5">WhatsApp Business API &middot; Templates &middot; Flows</p>
    </header>

    <!-- Tab Bar -->
    <nav class="flex bg-white border-b-2 border-gray-200 sticky top-[52px] z-40" id="tabBar">
        <button class="tab-btn flex-1 py-3 text-sm font-semibold text-gray-500 border-b-[3px] border-transparent
                       hover:text-wa hover:bg-gray-50 transition-all active"
                data-tab="conversations"
                hx-get="/ui/tab/conversations" hx-target="#content" hx-swap="innerHTML"
                onclick="setActive(this)">
            Conversations
        </button>
        <button class="tab-btn flex-1 py-3 text-sm font-semibold text-gray-500 border-b-[3px] border-transparent
                       hover:text-wa hover:bg-gray-50 transition-all"
                data-tab="templates"
                hx-get="/ui/tab/templates" hx-target="#content" hx-swap="innerHTML"
                onclick="setActive(this)">
            Templates
        </button>
        <button class="tab-btn flex-1 py-3 text-sm font-semibold text-gray-500 border-b-[3px] border-transparent
                       hover:text-wa hover:bg-gray-50 transition-all"
                data-tab="create"
                hx-get="/ui/tab/create-template" hx-target="#content" hx-swap="innerHTML"
                onclick="setActive(this)">
            Create Template
        </button>
        <button class="tab-btn flex-1 py-3 text-sm font-semibold text-gray-500 border-b-[3px] border-transparent
                       hover:text-wa hover:bg-gray-50 transition-all"
                data-tab="send"
                hx-get="/ui/tab/send-template" hx-target="#content" hx-swap="innerHTML"
                onclick="setActive(this)">
            Send Template
        </button>
        <button class="tab-btn flex-1 py-3 text-sm font-semibold text-gray-500 border-b-[3px] border-transparent
                       hover:text-wa hover:bg-gray-50 transition-all"
                data-tab="interactive"
                hx-get="/ui/tab/send-interactive" hx-target="#content" hx-swap="innerHTML"
                onclick="setActive(this)">
            Send List
        </button>
    </nav>

    <!-- Content -->
    <main class="max-w-4xl mx-auto px-4 py-5 min-h-[60vh]" id="content"
          hx-get="/ui/tab/conversations" hx-trigger="load" hx-swap="innerHTML">
        <div class="text-center py-10">
            <span class="inline-block w-5 h-5 border-2 border-gray-300 border-t-wa rounded-full spinner"></span>
            <span class="ml-2 text-gray-500 text-sm">Loading...</span>
        </div>
    </main>

    <script>
        function setActive(el) {
            document.querySelectorAll('.tab-btn').forEach(b => {
                b.classList.remove('active');
                b.classList.remove('text-wa', 'border-wa');
                b.classList.add('text-gray-500', 'border-transparent');
            });
            el.classList.add('active', 'text-wa', 'border-wa');
            el.classList.remove('text-gray-500', 'border-transparent');
        }
        // init first tab
        document.addEventListener('DOMContentLoaded', () => {
            const first = document.querySelector('.tab-btn.active');
            if (first) { first.classList.add('text-wa', 'border-wa'); first.classList.remove('text-gray-500', 'border-transparent'); }
        });
        function filterConvs() {
            const q = document.getElementById('convSearch').value.toLowerCase();
            document.querySelectorAll('[data-conv]').forEach(i => {
                i.style.display = (i.dataset.conv||'').toLowerCase().includes(q) ? '' : 'none';
            });
        }
    </script>
</body>
</html>
"""

# ──────────────────────────── TAB: CONVERSATIONS ────────────────────────────

CONVERSATIONS_TAB = """
<!-- Stats -->
<div class="flex flex-wrap gap-6 mb-5">
    <div class="text-center">
        <div class="text-2xl font-bold text-wa">{{ stats.total_conversations }}</div>
        <div class="text-[11px] text-gray-500 mt-0.5">Conversations</div>
    </div>
    <div class="text-center">
        <div class="text-2xl font-bold text-wa">{{ stats.total_messages }}</div>
        <div class="text-[11px] text-gray-500 mt-0.5">Messages</div>
    </div>
    <div class="text-center">
        <div class="text-2xl font-bold text-wa">{{ stats.total_bookings }}</div>
        <div class="text-[11px] text-gray-500 mt-0.5">Bookings</div>
    </div>
    <div class="text-center">
        <div class="text-2xl font-bold text-wa">R{{ stats.total_revenue }}</div>
        <div class="text-[11px] text-gray-500 mt-0.5">Revenue</div>
    </div>
</div>

<!-- Search -->
<input type="text" id="convSearch" placeholder="Search conversations..."
       oninput="filterConvs()"
       class="w-full px-4 py-2.5 rounded-lg bg-white shadow-sm text-sm outline-none
              focus:ring-2 focus:ring-wa/40 mb-4 border border-gray-200">

{% if conversations %}
    <div class="space-y-0.5">
    {% set colors = ['bg-wa-light', 'bg-sky-400', 'bg-red-400', 'bg-amber-500', 'bg-violet-500'] %}
    {% for c in conversations %}
        <div data-conv="{{ c.customer_name or c.wa_id }}"
             class="flex items-center gap-3.5 px-4 py-3 bg-white rounded-lg cursor-pointer
                    hover:bg-gray-50 transition-colors"
             hx-get="/ui/tab/chat/{{ c.wa_id }}" hx-target="#content" hx-swap="innerHTML">
            <div class="w-11 h-11 rounded-full flex items-center justify-center text-white
                        font-semibold text-lg shrink-0 {{ colors[loop.index0 % 5] }}">
                {{ (c.customer_name or c.wa_id)[0:1].upper() }}
            </div>
            <div class="flex-1 min-w-0">
                <div class="font-semibold text-sm truncate">{{ c.customer_name or c.wa_id }}</div>
                <div class="text-xs text-gray-500 truncate mt-0.5">{{ c.last_user_message or 'No messages yet' }}</div>
            </div>
            <div class="text-right shrink-0">
                <div class="text-[11px] text-gray-400">{{ c.last_message_at[:16] if c.last_message_at else '' }}</div>
                <span class="inline-block mt-1 bg-green-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
                    {{ c.message_count }}
                </span>
            </div>
        </div>
    {% endfor %}
    </div>
{% else %}
    <div class="text-center py-16 text-gray-400">
        <h4 class="text-gray-700 font-semibold mb-1">No conversations yet</h4>
        <p class="text-sm">Conversations appear when customers message the WhatsApp bot.</p>
    </div>
{% endif %}
"""

# ──────────────────────────── TAB: CHAT DETAIL ────────────────────────────

CHAT_DETAIL_TAB = """
<div class="bg-white rounded-xl shadow-sm overflow-hidden">
    <!-- Chat Header -->
    <div class="bg-wa text-white px-5 py-3 flex items-center gap-3">
        <span class="cursor-pointer text-xl hover:opacity-80 transition-opacity"
              hx-get="/ui/tab/conversations" hx-target="#content" hx-swap="innerHTML"
              onclick="document.querySelector('[data-tab=conversations]').click()">&larr;</span>
        <div class="flex-1">
            <div class="font-semibold">{{ customer_name or 'Unknown' }}</div>
            <div class="text-xs text-white/70">{{ wa_id }} &middot; {{ messages|length }} messages</div>
        </div>
        <button class="text-xs bg-white/20 hover:bg-white/30 text-white px-3 py-1.5 rounded-md
                       font-medium transition-colors"
                hx-get="/ui/tab/chat/{{ wa_id }}" hx-target="#content" hx-swap="innerHTML">
            Refresh
        </button>
    </div>

    <!-- Messages -->
    <div class="bg-wa-bg px-5 py-4 max-h-[60vh] overflow-y-auto chat-scroll" id="chatBody">
        {% set prev_date = namespace(val='') %}
        {% for m in messages %}
            {% set md = m.created_at[:10] if m.created_at else '' %}
            {% if md != prev_date.val %}
                <div class="text-center my-3.5">
                    <span class="bg-sky-100 text-gray-600 text-[11px] px-3 py-1 rounded-lg">{{ md }}</span>
                </div>
                {% set prev_date.val = md %}
            {% endif %}

            {% if m.role == 'tool' %}
                <div class="max-w-[85%] mb-1 mr-auto">
                    <div class="bg-amber-50 border-l-[3px] border-amber-400 rounded-lg rounded-tl-none
                                px-3 py-2 shadow-sm font-mono text-[11px]">
                        <span class="bg-amber-400 text-amber-900 text-[10px] font-semibold px-1.5 py-0.5 rounded">
                            TOOL{% if m.tool_call_id %} {{ m.tool_call_id[:10] }}{% endif %}
                        </span>
                        <pre class="whitespace-pre-wrap mt-1 text-gray-700">{{ m.content[:400] if m.content else '' }}{% if m.content and m.content|length > 400 %}...{% endif %}</pre>
                        <div class="text-[10px] text-gray-400 text-right mt-1">{{ m.created_at[11:16] if m.created_at else '' }}</div>
                    </div>
                </div>
            {% elif m.role == 'assistant' %}
                <div class="max-w-[70%] mb-1 mr-auto">
                    <div class="bg-white rounded-lg rounded-tl-none px-3 py-2 shadow-sm text-[13px] leading-relaxed">
                        <div class="text-[10px] uppercase font-semibold text-gray-400 tracking-wider mb-0.5">AI Agent</div>
                        <div class="text-gray-800">{{ m.content or '' }}</div>
                        {% if m.tool_calls %}<div class="text-[11px] text-gray-400 italic mt-1">Tools: {{ m.tool_calls }}</div>{% endif %}
                        <div class="text-[10px] text-gray-400 text-right mt-1">{{ m.created_at[11:16] if m.created_at else '' }}</div>
                    </div>
                </div>
            {% elif m.role == 'user' %}
                <div class="max-w-[70%] mb-1 ml-auto">
                    <div class="bg-wa-bubble rounded-lg rounded-tr-none px-3 py-2 shadow-sm text-[13px] leading-relaxed">
                        <div class="text-[10px] uppercase font-semibold text-gray-400 tracking-wider mb-0.5">Customer</div>
                        <div class="text-gray-800">{{ m.content or '[no text]' }}</div>
                        <div class="text-[10px] text-gray-400 text-right mt-1">{{ m.created_at[11:16] if m.created_at else '' }}</div>
                    </div>
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
    <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4 text-sm">{{ error }}</div>
{% endif %}

<div class="bg-white rounded-xl shadow-sm p-5">
    <h3 class="text-sm font-semibold text-wa mb-4">Message Templates ({{ templates|length }})</h3>
    {% if templates %}
    <div class="overflow-x-auto">
        <table class="w-full text-sm">
            <thead>
                <tr class="border-b-2 border-gray-200">
                    <th class="text-left text-[11px] uppercase text-gray-400 font-semibold px-3 py-2">Name</th>
                    <th class="text-left text-[11px] uppercase text-gray-400 font-semibold px-3 py-2">Category</th>
                    <th class="text-left text-[11px] uppercase text-gray-400 font-semibold px-3 py-2">Language</th>
                    <th class="text-left text-[11px] uppercase text-gray-400 font-semibold px-3 py-2">Status</th>
                    <th class="text-left text-[11px] uppercase text-gray-400 font-semibold px-3 py-2">Body</th>
                    <th class="px-3 py-2"></th>
                </tr>
            </thead>
            <tbody>
                {% for t in templates %}
                <tr class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                    <td class="px-3 py-2.5 font-semibold text-gray-800">{{ t.name }}</td>
                    <td class="px-3 py-2.5 text-gray-600">{{ t.category or '—' }}</td>
                    <td class="px-3 py-2.5 text-gray-600">{{ t.language or '—' }}</td>
                    <td class="px-3 py-2.5">
                        {% set st = (t.status or '')|lower %}
                        <span class="inline-block px-2 py-0.5 rounded-full text-[11px] font-semibold uppercase
                            {% if st=='approved' %}bg-green-100 text-green-700
                            {% elif st=='rejected' %}bg-red-100 text-red-700
                            {% elif st=='pending' %}bg-yellow-100 text-yellow-700
                            {% else %}bg-gray-100 text-gray-500{% endif %}">
                            {{ t.status or 'UNKNOWN' }}
                        </span>
                    </td>
                    <td class="px-3 py-2.5 text-xs text-gray-500 max-w-[280px] truncate">{{ t.body_text or '—' }}</td>
                    <td class="px-3 py-2.5">
                        <button class="bg-red-500 hover:bg-red-600 text-white text-xs font-semibold
                                       px-3 py-1 rounded-md transition-colors"
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
        <div class="text-center py-14 text-gray-400">
            <h4 class="text-gray-700 font-semibold mb-1">No templates found</h4>
            <p class="text-sm">Create one using the "Create Template" tab.</p>
        </div>
    {% endif %}
</div>
"""

# ──────────────────────────── TAB: CREATE TEMPLATE ────────────────────────────

CREATE_TEMPLATE_TAB = """
<div class="bg-white rounded-xl shadow-sm p-5">
    <h3 class="text-sm font-semibold text-wa mb-4">Create a New WhatsApp Template</h3>
    <div id="createResult"></div>
    <form class="grid grid-cols-1 sm:grid-cols-2 gap-3"
          hx-post="/ui/api/templates" hx-target="#createResult" hx-swap="innerHTML"
          hx-disabled-elt="button[type=submit]">
        <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">Template Name</label>
            <input type="text" name="name" placeholder="e.g. order_update" required pattern="[a-z0-9_]+"
                   title="Lowercase letters, numbers, and underscores only"
                   class="w-full px-3 py-2 border border-gray-200 rounded-md text-sm outline-none
                          focus:border-wa focus:ring-1 focus:ring-wa/30 transition-colors">
            <p class="text-[11px] text-gray-400 mt-1">Lowercase, no spaces. e.g. booking_confirm</p>
        </div>
        <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">Category</label>
            <select name="category" required
                    class="w-full px-3 py-2 border border-gray-200 rounded-md text-sm outline-none
                           focus:border-wa focus:ring-1 focus:ring-wa/30 transition-colors bg-white">
                <option value="MARKETING">Marketing</option>
                <option value="UTILITY" selected>Utility</option>
                <option value="AUTHENTICATION">Authentication</option>
            </select>
        </div>
        <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">Language</label>
            <select name="language" required
                    class="w-full px-3 py-2 border border-gray-200 rounded-md text-sm outline-none
                           focus:border-wa focus:ring-1 focus:ring-wa/30 transition-colors bg-white">
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
            <label class="block text-xs font-medium text-gray-500 mb-1">Header (optional)</label>
            <input type="text" name="header_text" placeholder="e.g. Booking Confirmation"
                   class="w-full px-3 py-2 border border-gray-200 rounded-md text-sm outline-none
                          focus:border-wa focus:ring-1 focus:ring-wa/30 transition-colors">
        </div>
        <div class="sm:col-span-2">
            <label class="block text-xs font-medium text-gray-500 mb-1">Body Text</label>
            <textarea name="body_text" required rows="3"
                      placeholder="Your booking {{1}} is confirmed for {{2}}.&#10;&#10;Use {{1}}, {{2}}, etc. for variables."
                      class="w-full px-3 py-2 border border-gray-200 rounded-md text-sm outline-none
                             focus:border-wa focus:ring-1 focus:ring-wa/30 transition-colors resize-y min-h-[80px]"></textarea>
            <p class="text-[11px] text-gray-400 mt-1">Use &#123;&#123;1&#125;&#125;, &#123;&#123;2&#125;&#125; for dynamic variables</p>
        </div>
        <div class="sm:col-span-2">
            <label class="block text-xs font-medium text-gray-500 mb-1">Footer (optional)</label>
            <input type="text" name="footer_text" placeholder="e.g. DriveEasy Car Rentals"
                   class="w-full px-3 py-2 border border-gray-200 rounded-md text-sm outline-none
                          focus:border-wa focus:ring-1 focus:ring-wa/30 transition-colors">
        </div>
        <div class="sm:col-span-2 text-right mt-2">
            <button type="submit"
                    class="bg-wa hover:bg-wa-dark text-white font-semibold text-sm px-6 py-2.5
                           rounded-md transition-colors disabled:opacity-60 disabled:cursor-not-allowed">
                Create Template
                <span class="htmx-indicator inline-block w-4 h-4 border-2 border-white/30 border-t-white
                             rounded-full spinner ml-1.5 align-middle"></span>
            </button>
        </div>
    </form>
</div>
"""

# ──────────────────────────── TAB: SEND TEMPLATE ────────────────────────────

SEND_TEMPLATE_TAB = """
<div class="bg-white rounded-xl shadow-sm p-5">
    <h3 class="text-sm font-semibold text-wa mb-4">Send a Template Message</h3>
    {% if error %}
        <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4 text-sm">{{ error }}</div>
    {% endif %}
    <div id="sendResult"></div>
    <form class="grid grid-cols-1 sm:grid-cols-2 gap-3"
          hx-post="/ui/api/send-template" hx-target="#sendResult" hx-swap="innerHTML"
          hx-disabled-elt="button[type=submit]">
        <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">Template Name</label>
            <select name="template_name" id="templateSelect" required
                    onchange="onTemplateNameChange(this)"
                    class="w-full px-3 py-2 border border-gray-200 rounded-md text-sm outline-none
                           focus:border-wa focus:ring-1 focus:ring-wa/30 transition-colors bg-white">
                <option value="" disabled selected>\u2014 Select a template \u2014</option>
                {% for name in template_names %}
                <option value="{{ name }}">{{ name }}{% if grouped[name][0].status != 'APPROVED' %} ({{ grouped[name][0].status }}){% endif %}</option>
                {% endfor %}
            </select>
            {% if not template_names %}
                <p class="text-[11px] text-amber-500 mt-1">No templates found \u2014 create one first</p>
            {% endif %}
        </div>
        <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">Recipient Phone Number</label>
            <input type="text" name="phone_number" placeholder="e.g. 27821234567" required
                   class="w-full px-3 py-2 border border-gray-200 rounded-md text-sm outline-none
                          focus:border-wa focus:ring-1 focus:ring-wa/30 transition-colors">
            <p class="text-[11px] text-gray-400 mt-1">With country code, no + or spaces</p>
        </div>
        <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">Language</label>
            <select name="language" id="langSelect" required
                    onchange="onLangChange(this)"
                    class="w-full px-3 py-2 border border-gray-200 rounded-md text-sm outline-none
                           focus:border-wa focus:ring-1 focus:ring-wa/30 transition-colors bg-white">
                <option value="" disabled selected>\u2014 Pick a template first \u2014</option>
            </select>
            <p class="text-[11px] text-gray-400 mt-1">Languages registered for the selected template</p>
        </div>
        <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">Body Variables (comma-separated)</label>
            <input type="text" name="variables" placeholder="e.g. #12345, try a redelivery"
                   class="w-full px-3 py-2 border border-gray-200 rounded-md text-sm outline-none
                          focus:border-wa focus:ring-1 focus:ring-wa/30 transition-colors">
            <p class="text-[11px] text-gray-400 mt-1">Leave empty if template has no variables</p>
        </div>
        <input type="hidden" name="has_flow" id="hasFlowInput" value="0">
        <!-- Template info badges -->
        <div class="sm:col-span-2" id="tplBadges" style="display:none">
            <span id="flowBadge" style="display:none"
                  class="inline-block bg-blue-100 text-blue-700 text-[11px] font-semibold px-2 py-0.5 rounded-full">
                \u26a1 Flow Button
            </span>
            <span id="noFlowBadge" style="display:none"
                  class="inline-block bg-gray-100 text-gray-500 text-[11px] font-semibold px-2 py-0.5 rounded-full">
                Standard Template (no flow)
            </span>
        </div>
        <!-- Template body preview -->
        <div class="sm:col-span-2" id="tplPreview" style="display:none">
            <label class="block text-xs font-medium text-gray-500 mb-1">Template Body Preview</label>
            <div id="tplPreviewBody" class="bg-gray-50 border border-gray-200 rounded-md px-3 py-2
                        text-sm text-gray-600 whitespace-pre-wrap"></div>
        </div>
        <div class="sm:col-span-2 text-right mt-2">
            <button type="submit"
                    class="bg-wa hover:bg-wa-dark text-white font-semibold text-sm px-6 py-2.5
                           rounded-md transition-colors disabled:opacity-60 disabled:cursor-not-allowed">
                Send Template
                <span class="htmx-indicator inline-block w-4 h-4 border-2 border-white/30 border-t-white
                             rounded-full spinner ml-1.5 align-middle"></span>
            </button>
        </div>
    </form>
</div>
<script>
    // Template data grouped by name, injected from server
    var _tplData = {{ grouped_json }};

    function onTemplateNameChange(sel) {
        var name = sel.value;
        var langSel = document.getElementById('langSelect');
        langSel.innerHTML = '';
        var variants = _tplData[name] || [];
        variants.forEach(function(v, i) {
            var opt = document.createElement('option');
            opt.value = v.language;
            opt.textContent = v.language;
            if (i === 0) opt.selected = true;
            langSel.appendChild(opt);
        });
        // update preview & flow flag for first language variant
        var first = variants.length ? variants[0] : null;
        showPreview(first ? first.body_text : '');
        updateFlowFlag(first);
    }

    function onLangChange(sel) {
        var nameSel = document.getElementById('templateSelect');
        var name = nameSel.value;
        var variants = _tplData[name] || [];
        var lang = sel.value;
        var match = variants.find(function(v){ return v.language === lang; });
        showPreview(match ? match.body_text : '');
        updateFlowFlag(match);
    }

    function updateFlowFlag(variant) {
        var hasFlow = variant && variant.has_flow;
        document.getElementById('hasFlowInput').value = hasFlow ? '1' : '0';
        var badges = document.getElementById('tplBadges');
        var flowBadge = document.getElementById('flowBadge');
        var noFlowBadge = document.getElementById('noFlowBadge');
        if (variant) {
            badges.style.display = '';
            flowBadge.style.display = hasFlow ? '' : 'none';
            noFlowBadge.style.display = hasFlow ? 'none' : '';
        } else {
            badges.style.display = 'none';
        }
    }

    function showPreview(body) {
        var preview = document.getElementById('tplPreview');
        var previewBody = document.getElementById('tplPreviewBody');
        if (body) {
            previewBody.textContent = body;
            preview.style.display = '';
        } else {
            preview.style.display = 'none';
        }
    }
</script>
"""

# ──────────────────────────── TAB: SEND INTERACTIVE LIST ────────────────────────────

SEND_INTERACTIVE_TAB = """
<div class="bg-white rounded-xl shadow-sm p-5">
    <h3 class="text-sm font-semibold text-wa mb-4">Send Interactive Service List</h3>
    <div id="interactiveResult"></div>
    <form class="grid grid-cols-1 gap-3"
          hx-post="/ui/api/send-interactive" hx-target="#interactiveResult" hx-swap="innerHTML"
          hx-disabled-elt="button[type=submit]">
        <div>
            <label class="block text-xs font-medium text-gray-500 mb-1">Recipient Phone Number</label>
            <input type="text" name="phone_number" placeholder="e.g. 27821234567" required
                   class="w-full px-3 py-2 border border-gray-200 rounded-md text-sm outline-none
                          focus:border-wa focus:ring-1 focus:ring-wa/30 transition-colors">
            <p class="text-[11px] text-gray-400 mt-1">With country code, no + or spaces</p>
        </div>

        <!-- Preview -->
        <div class="mt-2">
            <label class="block text-xs font-medium text-gray-500 mb-2">Preview</label>
            <div class="bg-wa-bg rounded-lg p-4 border border-gray-200">
                <div class="bg-white rounded-lg shadow-sm p-3 max-w-xs">
                    <div class="font-semibold text-sm text-gray-800 mb-1">What would you like today? \U0001f697</div>
                    <div class="text-xs text-gray-600 mb-2">Choose one service to proceed:</div>
                    <div class="space-y-1.5 mb-3">
                        <div class="flex items-center gap-2 text-xs text-gray-700">
                            <span class="w-5 h-5 rounded-full bg-wa/10 text-wa text-[10px] font-bold flex items-center justify-center">1</span>
                            Full Financing \U0001f4b0
                        </div>
                        <div class="flex items-center gap-2 text-xs text-gray-700">
                            <span class="w-5 h-5 rounded-full bg-wa/10 text-wa text-[10px] font-bold flex items-center justify-center">2</span>
                            Top Up \U0001f51d
                        </div>
                        <div class="flex items-center gap-2 text-xs text-gray-700">
                            <span class="w-5 h-5 rounded-full bg-wa/10 text-wa text-[10px] font-bold flex items-center justify-center">3</span>
                            Vehicle Inspection \U0001f50d
                        </div>
                        <div class="flex items-center gap-2 text-xs text-gray-700">
                            <span class="w-5 h-5 rounded-full bg-wa/10 text-wa text-[10px] font-bold flex items-center justify-center">4</span>
                            Chauffeur Service \U0001f468\u200d\u2708\ufe0f
                        </div>
                        <div class="flex items-center gap-2 text-xs text-gray-700">
                            <span class="w-5 h-5 rounded-full bg-wa/10 text-wa text-[10px] font-bold flex items-center justify-center">5</span>
                            Rent a Car \U0001f699
                        </div>
                    </div>
                    <div class="text-[10px] text-gray-400">DriveEasy Car Services</div>
                </div>
            </div>
        </div>

        <div class="text-right mt-2">
            <button type="submit"
                    class="bg-wa hover:bg-wa-dark text-white font-semibold text-sm px-6 py-2.5
                           rounded-md transition-colors disabled:opacity-60 disabled:cursor-not-allowed">
                Send Interactive List
                <span class="htmx-indicator inline-block w-4 h-4 border-2 border-white/30 border-t-white
                             rounded-full spinner ml-1.5 align-middle"></span>
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
    import json as _json
    error = None
    # grouped: { template_name: [ {language, status, body_text}, ... ] }
    grouped: dict[str, list[dict]] = {}
    try:
        raw = await list_templates()
        for tpl in raw:
            body_text = ""
            for comp in tpl.get("components", []):
                if comp.get("type") == "BODY":
                    body_text = comp.get("text", "")
                    break
            name = tpl.get("name", "")
            grouped.setdefault(name, []).append({
                "language":
                tpl.get("language", "en_US"),
                "status":
                tpl.get("status", ""),
                "body_text":
                body_text[:300],
                "has_flow":
                _has_flow_button(tpl),
            })
    except Exception as e:
        error = str(e)[:300]

    template_names = list(grouped.keys())

    from jinja2 import Template
    t = Template(SEND_TEMPLATE_TAB)
    return HTMLResponse(content=t.render(
        template_names=template_names,
        grouped=grouped,
        grouped_json=_json.dumps(grouped),
        error=error,
    ))


@router.get("/tab/send-interactive", response_class=HTMLResponse)
async def tab_send_interactive():
    return HTMLResponse(content=SEND_INTERACTIVE_TAB)


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
            '<div class="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg mb-4 text-sm">'
            f'Template <b>{name}</b> created successfully! ID: {tid}. '
            f'It will be reviewed by Meta before becoming active.</div>')
    except Exception as e:
        return HTMLResponse(
            f'<div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4 text-sm">'
            f'Failed to create template: {e}</div>')


@router.post("/api/send-template", response_class=HTMLResponse)
async def api_send_template(
        template_name: str = Form(...),
        phone_number: str = Form(...),
        language: str = Form("en_US"),
        variables: str = Form(""),
        has_flow: str = Form("0"),
):
    try:
        body_params = [v.strip() for v in variables.split(",")
                       if v.strip()] if variables.strip() else None
        await send_template_message(
            to=phone_number,
            template_name=template_name,
            language_code=language,
            body_parameters=body_params,
            has_flow_button=has_flow == "1",
        )
        return HTMLResponse(
            '<div class="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg mb-4 text-sm">'
            f'Template <b>{template_name}</b> sent to {phone_number} successfully!</div>'
        )
    except Exception as e:
        return HTMLResponse(
            f'<div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4 text-sm">'
            f'Failed to send: {e}</div>')


@router.post("/api/send-interactive", response_class=HTMLResponse)
async def api_send_interactive(phone_number: str = Form(...), ):
    try:
        await send_interactive_list(to=phone_number)
        return HTMLResponse(
            '<div class="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg mb-4 text-sm">'
            f'Interactive service list sent to <b>{phone_number}</b> successfully!</div>'
        )
    except Exception as e:
        return HTMLResponse(
            f'<div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4 text-sm">'
            f'Failed to send interactive list: {e}</div>')


@router.delete("/api/templates/{template_name}", response_class=HTMLResponse)
async def api_delete_template(template_name: str):
    try:
        await delete_template(template_name)
    except Exception as e:
        return HTMLResponse(
            f'<div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4 text-sm">'
            f'Delete failed: {e}</div>')
    return await tab_templates()
