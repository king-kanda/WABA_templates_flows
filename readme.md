Context
Build a full-service WhatsApp AI agent for a car rental business from scratch. The agent handles bookings, availability checks, FAQs, document collection (license photos), and booking reminders -- all via natural WhatsApp conversation powered by an LLM.
Tech Stack

Backend: Python + FastAPI
WhatsApp: Meta Cloud API (test number for dev)
AI/LLM: Groq (llama-3.3-70b-versatile)
Database: SQLite (via aiosqlite)
HTTP client: httpx (async)

Project Structure
WABA_templates_flows/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, lifespan, health endpoint
│   ├── config.py                # pydantic-settings, env vars
│   ├── database.py              # SQLite setup, table creation, query helpers
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── webhook.py           # GET (verify) + POST (incoming messages)
│   │   └── admin.py             # Vehicle CRUD, booking management, stats
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py           # Pydantic request/response models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── whatsapp.py          # Send messages, download media, mark read
│   │   ├── groq_agent.py        # System prompt, tool-call loop, conversation orchestration
│   │   ├── booking.py           # Create/cancel bookings, check availability
│   │   ├── vehicle.py           # Vehicle queries
│   │   ├── customer.py          # Customer lookup/creation
│   │   ├── conversation.py      # Load/save conversation history
│   │   ├── reminders.py         # Background task for pickup/return reminders
│   │   └── document.py          # Download & store license photos
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── definitions.py       # Groq tool schemas (check_availability, create_booking, etc.)
│   │   └── handlers.py          # Tool dispatch map + handler functions
│   ├── prompts/
│   │   └── system_prompt.txt    # Agent system prompt with business info + guidelines
│   └── data/
│       └── seed_vehicles.py     # Populate sample vehicle inventory
├── uploads/                     # Stored license photos organized by phone number
├── .env.example                 # Template for required env vars
├── requirements.txt             # 8 dependencies
└── Makefile                     # Convenience: make run, make seed
Database Schema (5 tables)

vehicles - id, make, model, year, category (economy/midsize/suv/luxury/bakkie), license_plate, daily_rate, status
customers - id, wa_id (WhatsApp number, unique), name, email, license_verified
bookings - id, reference (e.g. "BK-A3F7"), customer_id, vehicle_id, pickup_date, return_date, total_days, total_price, status, reminder flags
documents - id, customer_id, doc_type, file_path, wa_media_id
conversations - id, wa_id, role, content, tool_call_id, created_at (indexed)

AI Agent Design
The LLM acts as both the conversational interface AND the intent router via Groq's tool-calling:
6 Tools the agent can call:

check_availability(pickup_date, return_date, category?, vehicle_id?) - Find available vehicles
create_booking(wa_id, customer_name, vehicle_id, pickup_date, return_date) - Book a vehicle
get_customer_bookings(wa_id) - Look up customer's bookings
cancel_booking(reference, wa_id) - Cancel a booking (with ownership verification)
record_document(wa_id, doc_type, file_path) - Record uploaded license photo
get_vehicle_details(vehicle_id) - Get specific vehicle info

Agent loop: Load last 20 messages as context -> call Groq with system prompt + tools -> if tool call, execute and loop back -> if text response, send to customer. Max 5 iterations per message.
System prompt includes: business info (hours, location, policies, pricing tiers), FAQ answers, conversation guidelines (short messages, no markdown, confirm dates before booking, never hallucinate data).
Implementation Phases (build incrementally)
Phase 1: Foundation

Project structure, requirements.txt, config.py, database.py (all CREATE TABLE)
main.py with FastAPI app + lifespan + health check
Webhook GET verification endpoint
.env.example with all required vars

Phase 2: WhatsApp Echo Bot

services/whatsapp.py - send_text_message(), mark_as_read() via httpx
Webhook POST handler - parse incoming messages, echo them back
Message deduplication (in-memory set of recent message IDs)

Phase 3: Database + Seed Data

Full database.py with async query helpers (fetch_all, fetch_one, execute)
data/seed_vehicles.py - 10+ sample vehicles across all categories
services/vehicle.py and services/customer.py

Phase 4: Groq Agent (basic conversation)

prompts/system_prompt.txt with business info and guidelines
services/conversation.py - save/load message history
services/groq_agent.py - initial version WITHOUT tools (FAQ-only)
Wire webhook -> agent -> WhatsApp response

Phase 5: Tool Calling (availability + booking)

tools/definitions.py with check_availability + create_booking schemas
services/booking.py with business logic
tools/handlers.py with dispatch map
Add tool loop to groq_agent.py

Phase 6: Tool Calling (lookup + cancellation)

Add get_customer_bookings, cancel_booking, get_vehicle_details tools
Test full cycle: book -> check -> cancel

Phase 7: Document Upload

services/whatsapp.py - add download_media()
services/document.py - save files to uploads/{wa_id}/
Detect image message types in webhook, download before calling agent
Add record_document tool

Phase 8: Reminders

services/reminders.py - async background loop (hourly)
Send pickup reminders (day before) and return reminders (day before)
Hook into FastAPI lifespan

Phase 9: Admin Endpoints

routers/admin.py - vehicles CRUD, bookings list/cancel, customer list, stats
models/schemas.py - Pydantic validation models
API key auth via header dependency

Phase 10: Polish

Error handling, logging, edge cases (empty messages, unsupported types)
Rate limiting per wa_id
Makefile convenience targets

Dependencies (requirements.txt)
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
aiosqlite>=0.20.0
httpx>=0.27.0
groq>=0.11.0
pydantic-settings>=2.6.0
python-dotenv>=1.0.0
python-multipart>=0.0.12
Key Design Decisions

No ORM - Raw SQL via aiosqlite. 5 simple tables don't need SQLAlchemy overhead
No LangChain - Groq SDK has native tool calling. Agent loop is ~30 lines
LLM as intent router - No separate NLU layer. Adding features = adding tool definitions
Conversation in DB - Survives restarts, provides audit trail, spans multi-day conversations
httpx - Async HTTP to avoid blocking FastAPI's event loop

Verification

Run uvicorn app.main:app --reload and hit /health
Expose via ngrok, configure webhook in Meta dashboard, verify GET succeeds
Send WhatsApp message -> get echo back (Phase 2)
Chat with agent about FAQs -> get contextual answers (Phase 4)
Full booking flow via WhatsApp: check availability -> book -> look up -> cancel (Phases 5-6)
Send license photo -> confirm saved to uploads/ (Phase 7)
Create booking for tomorrow -> verify reminder fires (Phase 8)
Hit admin endpoints with curl/Postman (Phase 9)