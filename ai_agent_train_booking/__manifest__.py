# -*- coding: utf-8 -*-
{
    "name": "Agentic AI Train Ticket Booking",
    "version": "19.0.1.0.0",
    "category": "Operations/Travel",
    "summary": "Autonomous Agentic AI that searches, plans, books, and manages train tickets automatically with tool calling.",
    "description": """
Agentic AI Train Ticket Booking for Odoo 19
===========================================
This module brings autonomous Agentic AI to Odoo for automating end-to-end train reservations and travel workflows.

Key Highlights:
---------------
* **Autonomous Agentic Loop**: Instead of simple text generation, the AI Agent reasons, selects tools, checks seat availability in Odoo, calculates fares, reserves tickets, allocates berths, and confirms bookings autonomously.
* **Tool-Calling Architecture**: Includes pre-registered tools for searching trains, checking seats, creating bookings, confirming reservations, retrieving PNR status, and cancellations.
* **Multi-Provider AI Support**: Connect to OpenAI (GPT-4o), Google Gemini, Anthropic Claude, or local Ollama.
* **Deterministic Autonomous Engine**: Out-of-the-box local simulation engine that can execute complex booking requests without requiring external API keys.
* **Human-in-the-Loop Safeguards**: Switch between full autonomy (auto-confirm and charge) and supervised mode (proposes reservation for user approval).
* **Train Management**: Master catalogs for Stations, Trains, Routes, Running Days, Fares, and Seat Availability.
* **Passenger & PNR Lifecycle**: Passenger allocation, berth allocation (Lower, Upper, Side Lower, etc.), coach assignments, and unique PNR generation.
* **Interactive Agent Console**: Quick wizard to converse with the agent or issue complex natural language instructions.
* **Audit & Traceability**: Complete step-by-step trace showing Thought, Tool Call, Arguments, and Odoo Execution Result for every session.
    """,
    "author": "Antigravity AI",
    "website": "https://www.example.com",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/agent_security.xml",
        "security/ir.model.access.csv",
        "data/station_data.xml",
        "data/train_data.xml",
        "data/agent_tools_data.xml",
        "data/agent_config_data.xml",
        "data/automated_cron_data.xml",
        "views/train_station_views.xml",
        "views/train_train_views.xml",
        "views/train_booking_views.xml",
        "views/ai_agent_views.xml",
        "views/ai_agent_task_views.xml",
        "views/res_config_settings_views.xml",
        "views/irctc_credential_views.xml",
        "wizard/agent_prompt_wizard_views.xml",
        "wizard/train_payment_wizard_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
    "sequence": 15,
}
