# WABA Templates & Flows — WhatsApp AI Car Rental Agent

A full-service WhatsApp Business AI agent for a car rental company, built on the **Meta WhatsApp Business API (WABA)** using the **Graph API v21.0**. The agent handles bookings, availability checks, FAQs, document collection, template messaging, and booking reminders — all through natural WhatsApp conversation powered by an LLM.

---

## Meta WhatsApp Business Platform

This project integrates with the following Meta WABA capabilities:

### Graph API (Cloud API)
All WhatsApp communication goes through the **Meta Graph API Cloud-hosted endpoints**:

| Endpoint | Purpose |
|----------|---------|
| `POST /{phone-number-id}/messages` | Send text, template, and interactive messages |
| `GET /{media-id}` | Retrieve media URL for downloading customer uploads |
| `POST /{phone-number-id}/messages` (status) | Mark incoming messages as read |

Authentication is via a **long-lived System User Access Token** passed as a Bearer token.

### Message Templates
WhatsApp Business requires pre-approved **message templates** for initiating conversations outside the 24-hour customer service window. This project supports sending template messages with dynamic body variables through:

- A **REST endpoint** (`POST /ui/send-template`) for dispatching templates from the dashboard
- A **UI form** on the admin dashboard for sending templates manually
- Support for parameterized body variables (e.g. `{{1}}`, `{{2}}`)

Templates are created and managed in the **Meta Business Manager** under *WhatsApp Manager > Message Templates* and must be approved before use.

**Example — `demo` template with 2 body variables:**
```
Body: Your order {{1}} has been updated. Please {{2}}.
Sample: Your order #12345 has been updated. Please try a redelivery.
```

### WhatsApp Flows
WhatsApp Flows allow businesses to build structured, form-like interactions within WhatsApp (e.g. multi-step booking forms, surveys). While this project currently uses **LLM-driven natural conversation** for the booking flow, the architecture is designed to accommodate WhatsApp Flows for scenarios like:

- Structured vehicle selection with dropdowns
- Date picker–based booking forms
- Customer registration flows
- Feedback collection after rentals

Flows are configured in the Meta Business Manager and triggered via interactive messages using the Graph API.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12 + FastAPI |
| WhatsApp | Meta Cloud API (Graph API v21.0) |
| AI / LLM | Groq (`llama-3.3-70b-versatile`) |
| Database | SQLite via `aiosqlite` |
| HTTP Client | `httpx` (async) |
| Templating | Jinja2 (admin dashboard) |

---

## Project Structure

```
WABA_templates_flows/
├── app/
│   ├── main.py                  # FastAPI app, lifespan, health endpoint
│   ├── config.py                # Pydantic-settings, env vars
│   ├── database.py              # SQLite setup, table creation, query helpers
│   ├── routers/
│   │   ├── webhook.py           # GET (verify) + POST (incoming messages)
│   │   ├── admin.py             # Vehicle CRUD, booking management, stats
│   │   └── conversations_ui.py  # Web dashboard + template message sender
│   ├── models/
│   │   └── schemas.py           # Pydantic request/response models
│   ├── services/
│   │   ├── whatsapp.py          # Send text/template messages, download media
│   │   ├── groq_agent.py        # System prompt, tool-call loop, conversation orchestration
│   │   ├── booking.py           # Create/cancel bookings, check availability
│   │   ├── vehicle.py           # Vehicle queries
│   │   ├── customer.py          # Customer lookup/creation
│   │   ├── conversation.py      # Load/save conversation history
│   │   ├── reminders.py         # Background task for pickup/return reminders
│   │   └── document.py          # Download & store license photos
│   ├── tools/
│   │   ├── definitions.py       # Groq tool schemas (6 tools)
│   │   └── handlers.py          # Tool dispatch map + handler functions
│   ├── prompts/
│   │   └── system_prompt.txt    # Agent system prompt with business info
│   └── data/
│       └── seed_vehicles.py     # Populate sample vehicle inventory
├── uploads/                     # Stored license photos by phone number
├── .env                         # Environment variables (not committed)
├── .gitignore
├── requirements.txt
├── Makefile
└── readme.md
```

---

## Database Schema

| Table | Key Columns |
|-------|------------|
| `vehicles` | id, make, model, year, category, license_plate, daily_rate, status |
| `customers` | id, wa_id (WhatsApp number), name, email, license_verified |
| `bookings` | id, reference, customer_id, vehicle_id, pickup/return dates, total_price, status, reminder flags |
| `documents` | id, customer_id, doc_type, file_path, wa_media_id |
| `conversations` | id, wa_id, role, content, tool_call_id, tool_calls, created_at |

---

## AI Agent Design

The LLM acts as both the conversational interface and the intent router via **Groq's native tool-calling**:

### 6 Tools

| Tool | Description |
|------|-------------|
| `check_availability` | Find available vehicles for given dates and optional category |
| `create_booking` | Book a vehicle for a customer |
| `get_customer_bookings` | Look up a customer's bookings |
| `cancel_booking` | Cancel a booking with ownership verification |
| `record_document` | Record an uploaded driver's license photo |
| `get_vehicle_details` | Get details for a specific vehicle |

### Agent Loop
1. Load last 20 messages as context
2. Call Groq with system prompt + tools
3. If tool call → execute and loop back
4. If text response → send to customer via WhatsApp
5. Max 5 iterations per incoming message

---

## Setup

### 1. Prerequisites
- Python 3.12+
- A **Meta Developer Account** with a WhatsApp Business test number
- A **Groq API key** ([console.groq.com](https://console.groq.com))
- `ngrok` or similar tunnel for local webhook development

### 2. Clone & Install

```bash
git clone https://github.com/king-kanda/WABA_templates_flows.git
cd WABA_templates_flows
python -m venv .venv
source .venv/bin/activate
make install
```

### 3. Configure Environment

Create a `.env` file in the project root:

```env
META_API_TOKEN=your_meta_api_token_here
META_PHONE_NUMBER_ID=your_phone_number_id_here
WEBHOOK_VERIFY_TOKEN=your_webhook_verify_token_here
GROQ_API_KEY=your_groq_api_key_here
ADMIN_API_KEY=your_admin_api_key_here
DATABASE_PATH=data/car_rental.db
UPLOADS_DIR=uploads
LOG_LEVEL=INFO
```

### 4. Seed Database & Run

```bash
make seed    # Populate 13 sample vehicles
make run     # Start server on port 8000
```

### 5. Configure Meta Webhook

1. Expose your local server: `ngrok http 8000`
2. In **Meta Developer Dashboard** → WhatsApp → Configuration:
   - **Callback URL:** `https://your-ngrok-url/webhook`
   - **Verify Token:** same as `WEBHOOK_VERIFY_TOKEN` in `.env`
   - Subscribe to: `messages`

### 6. Create Message Templates

In **Meta Business Manager** → WhatsApp Manager → Message Templates:

1. Create a template named `demo`
2. Add body text with variables `{{1}}` and `{{2}}`
3. Submit for approval
4. Once approved, send from the dashboard at `/ui`

---

## Endpoints

### Public
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/webhook` | Meta webhook verification |
| POST | `/webhook` | Incoming WhatsApp messages |

### Dashboard (UI)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/ui` | Conversations dashboard + template sender |
| GET | `/ui/conversations/{wa_id}` | View full conversation thread |
| POST | `/ui/send-template` | Send a template message |

### Admin (requires `X-API-Key` header)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/vehicles` | List all vehicles |
| POST | `/admin/vehicles` | Add a vehicle |
| PUT | `/admin/vehicles/{id}` | Update a vehicle |
| DELETE | `/admin/vehicles/{id}` | Delete a vehicle |
| GET | `/admin/bookings` | List all bookings |
| POST | `/admin/bookings/cancel` | Cancel a booking |
| GET | `/admin/customers` | List all customers |
| GET | `/admin/stats` | Dashboard statistics |

---

## Key Design Decisions

- **No ORM** — Raw SQL via `aiosqlite`. 5 simple tables don't need SQLAlchemy overhead
- **No LangChain** — Groq SDK has native tool calling. The agent loop is ~30 lines
- **LLM as intent router** — No separate NLU layer. Adding features = adding tool definitions
- **Conversation in DB** — Survives restarts, provides audit trail, spans multi-day conversations
- **httpx** — Async HTTP to avoid blocking FastAPI's event loop
- **Message deduplication** — In-memory dedup with TTL + per-message processing locks to prevent double responses from Meta's webhook retries

---

## License

MIT
