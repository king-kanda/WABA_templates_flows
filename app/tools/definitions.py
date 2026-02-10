"""Groq tool schemas for the car rental agent."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description":
            "Check available vehicles for rental between specified dates. Optionally filter by vehicle category or specific vehicle ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pickup_date": {
                        "type": "string",
                        "description": "Pickup date in YYYY-MM-DD format",
                    },
                    "return_date": {
                        "type": "string",
                        "description": "Return date in YYYY-MM-DD format",
                    },
                    "category": {
                        "type": "string",
                        "description":
                        "Vehicle category filter: economy, midsize, suv, luxury, or bakkie",
                        "enum":
                        ["economy", "midsize", "suv", "luxury", "bakkie"],
                    },
                    "vehicle_id": {
                        "type":
                        "integer",
                        "description":
                        "Specific vehicle ID to check availability for",
                    },
                },
                "required": ["pickup_date", "return_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_booking",
            "description":
            "Create a new vehicle rental booking for a customer.",
            "parameters": {
                "type":
                "object",
                "properties": {
                    "wa_id": {
                        "type": "string",
                        "description": "Customer's WhatsApp phone number",
                    },
                    "customer_name": {
                        "type": "string",
                        "description": "Customer's full name",
                    },
                    "vehicle_id": {
                        "type": "integer",
                        "description": "ID of the vehicle to book",
                    },
                    "pickup_date": {
                        "type": "string",
                        "description": "Pickup date in YYYY-MM-DD format",
                    },
                    "return_date": {
                        "type": "string",
                        "description": "Return date in YYYY-MM-DD format",
                    },
                },
                "required": [
                    "wa_id", "customer_name", "vehicle_id", "pickup_date",
                    "return_date"
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_bookings",
            "description":
            "Look up all bookings for a customer by their WhatsApp number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "wa_id": {
                        "type": "string",
                        "description": "Customer's WhatsApp phone number",
                    },
                },
                "required": ["wa_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_booking",
            "description":
            "Cancel an existing booking by reference number. Verifies the booking belongs to the customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reference": {
                        "type": "string",
                        "description":
                        "Booking reference number (e.g. BK-A3F7)",
                    },
                    "wa_id": {
                        "type":
                        "string",
                        "description":
                        "Customer's WhatsApp phone number for ownership verification",
                    },
                },
                "required": ["reference", "wa_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_document",
            "description":
            "Record that a customer has uploaded a document (e.g., driver's license photo).",
            "parameters": {
                "type": "object",
                "properties": {
                    "wa_id": {
                        "type": "string",
                        "description": "Customer's WhatsApp phone number",
                    },
                    "doc_type": {
                        "type": "string",
                        "description":
                        "Type of document, e.g. 'drivers_license'",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path where the document was saved",
                    },
                },
                "required": ["wa_id", "doc_type", "file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_vehicle_details",
            "description":
            "Get detailed information about a specific vehicle by ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "vehicle_id": {
                        "type": "integer",
                        "description": "The vehicle ID to get details for",
                    },
                },
                "required": ["vehicle_id"],
            },
        },
    },
]
